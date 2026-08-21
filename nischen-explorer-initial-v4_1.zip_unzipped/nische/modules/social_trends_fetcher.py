"""Platform-native social trend and hashtag sources.

Only documented/public APIs are used. Sources that require platform app review,
OAuth scopes or business accounts are explicitly disabled until configured.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from .http import request_json_async
from .models import SourceResult


def _tag(keyword: str) -> str:
    token = re.sub(r"[^\w]+", "", (keyword or "").lower(), flags=re.UNICODE)
    return token


async def fetch_x_trends(region: str = "DE", timeout: int = 20, limit: int = 20):
    bearer = os.getenv("X_BEARER_TOKEN")
    if not bearer:
        return SourceResult("X Trends", "disabled", error="X_BEARER_TOKEN fehlt")
    woeid = {
        "DE": 23424829, "AT": 23424750, "CH": 23424957, "FR": 23424819,
        "IT": 23424853, "ES": 23424950, "GB": 23424975, "US": 23424977,
        "NL": 23424909, "WORLD": 1,
    }.get((region or "DE").upper(), 1)
    try:
        data, latency = await request_json_async(
            "GET", f"https://api.x.com/2/trends/by/woeid/{woeid}",
            headers={"Authorization": f"Bearer {bearer}"},
            params={"max_trends": min(max(limit, 1), 50), "trend.fields": "trend_name,tweet_count"},
            timeout=timeout,
        )
        records = []
        for rank, item in enumerate(data.get("data") or [], 1):
            name = item.get("trend_name", "")
            records.append({
                "id": f"{woeid}:{name}", "source": "X Trends", "kind": "hashtag_trend",
                "platform": "X", "trend_name": name, "hashtag": name if str(name).startswith("#") else "",
                "rank": rank, "tweet_count": item.get("tweet_count"), "region": region,
                "date": datetime.now(timezone.utc).isoformat(),
                "url": f"https://x.com/search?q={quote(name)}&src=trend_click",
            })
        return SourceResult("X Trends", "ok" if records else "empty", records,
                            latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("X Trends", "error", error=str(exc))


async def fetch_instagram_hashtag(keyword: str, timeout: int = 20, limit: int = 50):
    token = os.getenv("META_ACCESS_TOKEN")
    ig_user_id = os.getenv("INSTAGRAM_BUSINESS_USER_ID")
    if not token or not ig_user_id:
        return SourceResult("Instagram Hashtags", "disabled",
                            error="META_ACCESS_TOKEN und INSTAGRAM_BUSINESS_USER_ID fehlen")
    tag = _tag(keyword)
    if not tag:
        return SourceResult("Instagram Hashtags", "empty")
    base = f"https://graph.facebook.com/{os.getenv("META_GRAPH_VERSION", "v25.0")}"
    try:
        lookup, latency1 = await request_json_async(
            "GET", f"{base}/ig_hashtag_search",
            params={"user_id": ig_user_id, "q": tag, "access_token": token}, timeout=timeout)
        ids = lookup.get("data") or []
        if not ids:
            return SourceResult("Instagram Hashtags", "empty", latency_ms=latency1, total_available=0)
        hashtag_id = ids[0].get("id")
        fields = "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count"
        recent, latency2 = await request_json_async(
            "GET", f"{base}/{hashtag_id}/recent_media",
            params={"user_id": ig_user_id, "fields": fields, "limit": min(limit, 50), "access_token": token}, timeout=timeout)
        top, latency3 = await request_json_async(
            "GET", f"{base}/{hashtag_id}/top_media",
            params={"user_id": ig_user_id, "fields": fields, "limit": min(limit, 50), "access_token": token}, timeout=timeout)
        records = []
        seen = set()
        for rank, media in enumerate((top.get("data") or []) + (recent.get("data") or []), 1):
            mid = str(media.get("id") or "")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            records.append({
                "id": mid, "source": "Instagram Hashtags", "kind": "hashtag_media", "platform": "Instagram",
                "hashtag": f"#{tag}", "caption": media.get("caption", ""), "media_type": media.get("media_type", ""),
                "likes": media.get("like_count", 0), "comments": media.get("comments_count", 0),
                "date": media.get("timestamp", ""), "url": media.get("permalink", ""), "rank": rank,
                "hashtag_id": hashtag_id,
            })
        return SourceResult("Instagram Hashtags", "ok" if records else "empty", records,
                            latency_ms=latency1 + latency2 + latency3, total_available=len(records))
    except Exception as exc:
        return SourceResult("Instagram Hashtags", "error", error=str(exc))


async def fetch_pinterest_trends(region: str = "DE", trend_type: str = "growing", timeout: int = 20, limit: int = 50):
    token = os.getenv("PINTEREST_ACCESS_TOKEN")
    if not token:
        return SourceResult("Pinterest Trends", "disabled", error="PINTEREST_ACCESS_TOKEN fehlt")
    region = (os.getenv("PINTEREST_REGION") or region or "DE").upper()
    try:
        data, latency = await request_json_async(
            "GET", f"https://api.pinterest.com/v5/trends/keywords/{quote(region, safe='+')}/top/{trend_type}",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": min(max(limit, 1), 50), "normalize_against_group": "true"}, timeout=timeout)
        records = []
        for rank, item in enumerate(data.get("trends") or [], 1):
            ts = item.get("time_series") or {}
            records.append({
                "id": f"{region}:{trend_type}:{item.get('keyword')}", "source": "Pinterest Trends",
                "kind": "hashtag_trend", "platform": "Pinterest", "keyword": item.get("keyword", ""),
                "hashtag": "#" + re.sub(r"\s+", "", str(item.get("keyword", ""))), "rank": rank,
                "growth_wow": item.get("pct_growth_wow"), "growth_mom": item.get("pct_growth_mom"),
                "growth_yoy": item.get("pct_growth_yoy"), "time_series": ts, "region": region,
                "trend_type": trend_type, "date": datetime.now(timezone.utc).isoformat(),
                "url": "https://trends.pinterest.com/",
            })
        return SourceResult("Pinterest Trends", "ok" if records else "empty", records,
                            latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("Pinterest Trends", "error", error=str(exc))


async def fetch_facebook_pages(keyword: str, timeout: int = 20, limit: int = 100):
    """Fetch configured Facebook Page feeds and classify hashtag matches.

    Facebook does not expose a general public-post hashtag search in the current
    Graph API. We therefore never pretend that page feeds are platform-wide trends.
    """
    token = os.getenv("META_ACCESS_TOKEN")
    page_ids = [x.strip() for x in (os.getenv("FACEBOOK_PAGE_IDS") or "").split(",") if x.strip()]
    if not token or not page_ids:
        return SourceResult("Facebook Pages", "disabled",
                            error="META_ACCESS_TOKEN und FACEBOOK_PAGE_IDS fehlen; keine globale FB-Hashtag-Suche verfügbar")
    records = []
    latencies = []
    for page_id in page_ids[:20]:
        try:
            data, latency = await request_json_async(
                "GET", f"https://graph.facebook.com/{os.getenv("META_GRAPH_VERSION", "v25.0")}/{page_id}/feed",
                params={"access_token": token,
                        "fields": "id,message,created_time,permalink_url,shares,comments.summary(true),reactions.summary(true)",
                        "limit": min(limit, 100)}, timeout=timeout)
            latencies.append(latency)
            for item in data.get("data") or []:
                text = item.get("message", "") or ""
                if keyword.lower() not in text.lower() and (f"#{_tag(keyword)}" not in text.lower().replace(" ", "")):
                    continue
                records.append({
                    "id": item.get("id"), "source": "Facebook Pages", "kind": "social",
                    "platform": "Facebook", "text": text, "date": item.get("created_time", ""),
                    "url": item.get("permalink_url", ""), "page_id": page_id,
                    "likes": ((item.get("reactions") or {}).get("summary") or {}).get("total_count", 0),
                    "comments": ((item.get("comments") or {}).get("summary") or {}).get("total_count", 0),
                    "hashtag": f"#{_tag(keyword)}",
                })
        except Exception as exc:
            return SourceResult("Facebook Pages", "error", error=str(exc), records=records,
                                latency_ms=sum(latencies) if latencies else None)
    return SourceResult("Facebook Pages", "ok" if records else "empty", records,
                        latency_ms=sum(latencies) if latencies else 0, total_available=len(records))
