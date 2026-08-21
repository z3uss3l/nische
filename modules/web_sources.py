"""Generic feeds, URL requests and respectful same-domain crawling.

Only HTTP(S) is accepted. Crawling checks robots.txt, stays on the seed domain,
uses bounded depth/page counts, and never attempts login/CAPTCHA/anti-bot bypass.
Use only URLs you are permitted to access.
"""
from __future__ import annotations

import asyncio
import os
import re
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, quote
from urllib import robotparser
import xml.etree.ElementTree as ET

from .http import request_text_async
from .models import SourceResult


def _urls(env_name: str) -> list[str]:
    return [x.strip() for x in (os.getenv(env_name) or "").split(",") if x.strip()]


def _safe_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in {"http", "https"} and bool(p.netloc)


class _HTMLExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.text_parts = []
        self.links = []
        self._title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower(); attrs = dict(attrs)
        if tag == "title": self._title = True
        if tag in {"script", "style", "noscript", "template", "svg"}: self._skip += 1
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title": self._title = False
        if tag in {"script", "style", "noscript", "template", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip: return
        text = re.sub(r"\s+", " ", data).strip()
        if not text: return
        self.text_parts.append(text)
        if self._title: self.title_parts.append(text)

    @property
    def title(self): return " ".join(self.title_parts).strip()
    @property
    def text(self): return " ".join(self.text_parts).strip()


def _feed_entries(text: str):
    """Minimal RSS 2.x + Atom parser with no third-party dependency."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}
    entries = []
    if root.tag.lower().endswith("rss"):
        for item in root.findall(".//item"):
            entries.append({
                "id": item.findtext("guid") or item.findtext("link") or item.findtext("title") or "",
                "title": item.findtext("title") or "", "text": item.findtext("description") or "",
                "date": item.findtext("pubDate") or item.findtext("dc:date", namespaces=ns) or "",
                "url": item.findtext("link") or "", "author": item.findtext("author") or "",
            })
    else:
        for item in root.findall("a:entry", ns):
            link = ""
            for ln in item.findall("a:link", ns):
                href = ln.attrib.get("href")
                if href: link = href; break
            entries.append({
                "id": item.findtext("a:id", default="", namespaces=ns) or link,
                "title": item.findtext("a:title", default="", namespaces=ns),
                "text": item.findtext("a:summary", default="", namespaces=ns) or item.findtext("a:content", default="", namespaces=ns),
                "date": item.findtext("a:published", default="", namespaces=ns) or item.findtext("a:updated", default="", namespaces=ns),
                "url": link, "author": (item.findtext("a:author/a:name", default="", namespaces=ns) or ""),
            })
    return entries


async def fetch_configured_feeds(keyword: str, timeout: int = 20):
    urls = _urls("FEED_URLS")
    if not urls:
        return SourceResult("Configured Feeds", "disabled", error="FEED_URLS nicht konfiguriert")
    records, latencies = [], []
    for template in urls[:50]:
        url = template.replace("{keyword}", quote(keyword))
        if not _safe_url(url): continue
        try:
            text, latency = await request_text_async("GET", url, timeout=timeout)
            latencies.append(latency)
            for entry in _feed_entries(text)[:200]:
                records.append({"id": entry["id"] or entry["url"], "source": "Configured Feeds", "kind": "feed",
                                "title": entry["title"], "text": entry["text"], "date": entry["date"],
                                "url": entry["url"], "feed_url": url, "author": entry["author"]})
        except Exception:
            continue
    return SourceResult("Configured Feeds", "ok" if records else "empty", records,
                        latency_ms=sum(latencies) if latencies else 0, total_available=len(records))


async def fetch_configured_urls(keyword: str, timeout: int = 20):
    urls = _urls("URL_REQUESTS")
    if not urls:
        return SourceResult("Configured URLs", "disabled", error="URL_REQUESTS nicht konfiguriert")
    records, latencies = [], []
    for template in urls[:50]:
        url = template.replace("{keyword}", quote(keyword))
        if not _safe_url(url): continue
        try:
            text, latency = await request_text_async("GET", url, timeout=timeout)
            latencies.append(latency)
            parser = _HTMLExtractor(); parser.feed(text)
            records.append({"id": url, "source": "Configured URLs", "kind": "web", "title": parser.title,
                            "text": parser.text[:12000], "url": url, "date": datetime.now(timezone.utc).isoformat()})
        except Exception:
            continue
    return SourceResult("Configured URLs", "ok" if records else "empty", records,
                        latency_ms=sum(latencies) if latencies else 0, total_available=len(records))


async def _robots_allowed(url: str, user_agent: str) -> bool:
    p = urlparse(url); robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        text, _ = await request_text_async("GET", robots_url, timeout=8)
        rp = robotparser.RobotFileParser(); rp.set_url(robots_url); rp.parse(text.splitlines())
        return rp.can_fetch(user_agent, url)
    except Exception:
        return False


async def crawl_configured_sites(keyword: str, timeout: int = 20):
    seeds = _urls("CRAWL_URLS")
    if not seeds:
        return SourceResult("Web Crawler", "disabled", error="CRAWL_URLS nicht konfiguriert")
    max_pages = min(max(int(os.getenv("CRAWL_MAX_PAGES", "20")), 1), 100)
    max_depth = min(max(int(os.getenv("CRAWL_MAX_DEPTH", "1")), 0), 3)
    ua = os.getenv("CRAWL_USER_AGENT", "Nischen-Explorer/4.0 (+respectful crawler)")
    q = keyword.lower(); records, visited, latencies = [], set(), []
    for seed in seeds[:20]:
        if not _safe_url(seed): continue
        seed_host = urlparse(seed).netloc; queue = deque([(seed, 0)])
        while queue and len(visited) < max_pages:
            url, depth = queue.popleft()
            if url in visited or urlparse(url).netloc != seed_host: continue
            visited.add(url)
            if not await _robots_allowed(url, ua): continue
            try:
                text, latency = await request_text_async("GET", url, timeout=timeout, headers={"User-Agent": ua})
                latencies.append(latency)
                parser = _HTMLExtractor(); parser.feed(text)
                if q in f"{parser.title} {parser.text}".lower():
                    records.append({"id": url, "source": "Web Crawler", "kind": "web", "title": parser.title,
                                    "text": parser.text[:12000], "url": url,
                                    "date": datetime.now(timezone.utc).isoformat(), "crawl_depth": depth})
                if depth < max_depth:
                    for href in parser.links:
                        child = urljoin(url, href); parsed = urlparse(child)
                        if parsed.scheme in {"http", "https"} and parsed.netloc == seed_host:
                            child = parsed._replace(fragment="").geturl()
                            if child not in visited: queue.append((child, depth + 1))
            except Exception:
                continue
    return SourceResult("Web Crawler", "ok" if records else "empty", records,
                        latency_ms=sum(latencies) if latencies else 0, total_available=len(records))
