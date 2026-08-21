from datetime import datetime, timedelta, timezone
import os
from .http import request_json
from .models import SourceResult


def _date_cutoff(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


def fetch_gdelt(keyword, days=7, timeout=15):
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {"query": keyword, "format": "json", "timespan": f"{days}d", "maxrecords": 100, "sort": "HybridRel"}
    try:
        data, latency = request_json("GET", url, params=params, timeout=timeout)
        records = []
        for a in data.get("articles", []):
            records.append({
                "id": a.get("url") or a.get("title"), "source": "GDELT", "kind": "news",
                "title": a.get("title", "").strip(), "source_name": a.get("domain") or a.get("source", ""),
                "date": a.get("seendate", ""), "url": a.get("url", ""), "language": a.get("language", ""),
                "country": a.get("sourcecountry", ""), "snippet": "",
            })
        return SourceResult("GDELT", "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("GDELT", "error", error=str(exc))


def fetch_gnews(keyword, days=7, language="de", country="de", timeout=15):
    key = os.getenv("GNEWS_API_KEY")
    if not key:
        return SourceResult("GNews", "disabled", error="GNEWS_API_KEY fehlt")
    url = "https://gnews.io/api/v4/search"
    params = {"q": keyword, "token": key, "lang": language, "country": country, "max": 100,
              "from": (_date_cutoff(days)).isoformat()}
    try:
        data, latency = request_json("GET", url, params=params, timeout=timeout)
        records = [{
            "id": a.get("url") or a.get("title"), "source": "GNews", "kind": "news",
            "title": a.get("title", "").strip(), "source_name": (a.get("source") or {}).get("name", ""),
            "date": a.get("publishedAt", ""), "url": a.get("url", ""), "language": language,
            "country": country, "snippet": a.get("description", "") or "",
        } for a in data.get("articles", [])]
        return SourceResult("GNews", "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("GNews", "error", error=str(exc))


def fetch_thenews(keyword, days=7, language="de", timeout=15):
    key = os.getenv("THENEWS_API_KEY")
    if not key:
        return SourceResult("TheNewsAPI", "disabled", error="THENEWS_API_KEY fehlt")
    url = "https://api.thenewsapi.com/v1/news/all"
    params = {"api_token": key, "search": keyword, "language": language, "limit": 50,
              "published_after": _date_cutoff(days).strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        data, latency = request_json("GET", url, params=params, timeout=timeout)
        records = [{
            "id": a.get("uuid") or a.get("url"), "source": "TheNewsAPI", "kind": "news",
            "title": a.get("title", "").strip(), "source_name": a.get("source", ""),
            "date": a.get("published_at", ""), "url": a.get("url", ""),
            "language": a.get("language", language), "country": "", "snippet": a.get("snippet", "") or a.get("description", "") or "",
        } for a in data.get("data", [])]
        return SourceResult("TheNewsAPI", "ok" if records else "empty", records, latency_ms=latency, total_available=(data.get("meta") or {}).get("found"))
    except Exception as exc:
        return SourceResult("TheNewsAPI", "error", error=str(exc))
