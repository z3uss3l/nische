import os
from datetime import datetime, timezone, timedelta
from .http import request_json
from .models import SourceResult


def fetch_x_twitter(keyword, days=7, limit=100, timeout=20):
    bearer = os.getenv("X_BEARER_TOKEN")
    if not bearer:
        return SourceResult("X", "disabled", error="X_BEARER_TOKEN fehlt")
    start = datetime.now(timezone.utc) - timedelta(days=min(days, 7))
    url = "https://api.x.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer}"}
    params = {"query": f'({keyword}) -is:retweet', "max_results": min(max(limit, 10), 100),
              "start_time": start.isoformat().replace("+00:00", "Z"),
              "tweet.fields": "created_at,public_metrics,lang,author_id"}
    try:
        data, latency = request_json("GET", url, headers=headers, params=params, timeout=timeout)
        records = []
        for t in data.get("data", []):
            metrics = t.get("public_metrics") or {}
            records.append({"id": t.get("id"), "source": "X", "kind": "social", "text": t.get("text", ""),
                            "date": t.get("created_at", ""), "likes": metrics.get("like_count", 0),
                            "reposts": metrics.get("retweet_count", 0), "replies": metrics.get("reply_count", 0),
                            "lang": t.get("lang", ""), "url": f"https://x.com/i/web/status/{t.get('id')}"})
        return SourceResult("X", "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("X", "error", error=str(exc))


def fetch_configured_connector(name, keyword, days=7, timeout=20):
    endpoint = os.getenv(f"{name.upper()}_ENDPOINT")
    api_key = os.getenv(f"{name.upper()}_API_KEY")
    if not endpoint or not api_key:
        return SourceResult(name, "disabled", error=f"{name.upper()}_ENDPOINT und API-Key nicht konfiguriert")
    try:
        data, latency = request_json("GET", endpoint, headers={"Authorization": f"Bearer {api_key}"},
                                     params={"q": keyword, "query": keyword, "days": days}, timeout=timeout)
        items = data.get("results") or data.get("items") or data.get("mentions") or []
        records = [{"id": str(i.get("id") or i.get("url") or i.get("text", ""))[:200], "source": name,
                    "kind": "social", "text": i.get("text", ""), "platform": i.get("platform") or i.get("source", ""),
                    "sentiment": i.get("sentiment", "neutral"), "intent": i.get("intent", "other"),
                    "date": i.get("date") or i.get("created_at", ""), "url": i.get("url", "")}
                   for i in items if isinstance(i, dict)]
        return SourceResult(name, "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult(name, "error", error=str(exc))
