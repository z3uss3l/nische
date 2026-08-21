"""YouTube Data API v3 source."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from .http import request_json_async
from .models import SourceResult


async def fetch_youtube(keyword: str, region: str = "DE", days: int = 30, timeout: int = 20, limit: int = 50):
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return SourceResult("YouTube", "disabled", error="YOUTUBE_API_KEY fehlt")
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    try:
        data, latency1 = await request_json_async(
            "GET", "https://www.googleapis.com/youtube/v3/search",
            params={"key": key, "part": "snippet", "q": keyword, "type": "video",
                    "order": os.getenv("YOUTUBE_ORDER", "relevance"),
                    "maxResults": min(max(limit, 1), 50), "regionCode": region,
                    "publishedAfter": cutoff.isoformat().replace("+00:00", "Z")}, timeout=timeout)
        ids = [x.get("id", {}).get("videoId") for x in data.get("items") or [] if x.get("id", {}).get("videoId")]
        if not ids:
            return SourceResult("YouTube", "empty", latency_ms=latency1, total_available=(data.get("pageInfo") or {}).get("totalResults", 0))
        data2, latency2 = await request_json_async(
            "GET", "https://www.googleapis.com/youtube/v3/videos",
            params={"key": key, "part": "snippet,statistics,contentDetails", "id": ",".join(ids)}, timeout=timeout)
        records = []
        for item in data2.get("items") or []:
            sn = item.get("snippet") or {}; st = item.get("statistics") or {}
            records.append({
                "id": item.get("id"), "source": "YouTube", "kind": "video", "platform": "YouTube",
                "title": sn.get("title", ""), "description": sn.get("description", ""),
                "channel_id": sn.get("channelId", ""), "channel_title": sn.get("channelTitle", ""),
                "published_at": sn.get("publishedAt", ""), "date": sn.get("publishedAt", ""),
                "views": int(st.get("viewCount") or 0), "likes": int(st.get("likeCount") or 0),
                "comments": int(st.get("commentCount") or 0), "tags": sn.get("tags") or [],
                "url": f"https://www.youtube.com/watch?v={item.get('id')}",
                "thumbnail": ((sn.get("thumbnails") or {}).get("high") or {}).get("url", ""),
            })
        return SourceResult("YouTube", "ok" if records else "empty", records,
                            latency_ms=latency1 + latency2,
                            total_available=(data.get("pageInfo") or {}).get("totalResults", len(records)))
    except Exception as exc:
        return SourceResult("YouTube", "error", error=str(exc))
