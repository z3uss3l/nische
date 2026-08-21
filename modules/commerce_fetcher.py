"""Commerce, price comparison and local-service discovery via DataForSEO Merchant/SERP APIs."""
from __future__ import annotations

import asyncio
import os
from .http import request_json_async
from .models import SourceResult

BASE = "https://api.dataforseo.com/v3"


def _creds():
    return os.getenv("DATAFORSEO_USERNAME"), os.getenv("DATAFORSEO_PASSWORD")


async def fetch_google_shopping(keyword: str, region: str = "DE", timeout: int = 45, limit: int = 40):
    username, password = _creds()
    if not username or not password:
        return SourceResult("Google Shopping", "disabled", error="DATAFORSEO_USERNAME/DATAFORSEO_PASSWORD fehlen")
    location = int(os.getenv("DATAFORSEO_SHOPPING_LOCATION_CODE", os.getenv("DATAFORSEO_LOCATION_CODE", "2276")))
    language = os.getenv("DATAFORSEO_SHOPPING_LANGUAGE_CODE", os.getenv("DATAFORSEO_LANGUAGE_CODE", "de"))
    payload = [{"language_code": language, "location_code": location, "keyword": keyword,
                "sort_by": "relevance", "depth": min(max(limit, 10), 100)}]
    try:
        posted, latency1 = await request_json_async("POST", f"{BASE}/merchant/google/products/task_post",
                                                      auth=(username, password), json=payload, timeout=timeout)
        task_id = ((posted.get("tasks") or [{}])[0]).get("id")
        if not task_id:
            return SourceResult("Google Shopping", "empty", latency_ms=latency1)
        # Merchant Standard method is asynchronous. Poll the task-specific GET endpoint,
        # never treat task_post's null result as a completed response.
        max_polls = max(1, int(os.getenv("DATAFORSEO_MERCHANT_MAX_POLLS", "6")))
        delay = float(os.getenv("DATAFORSEO_MERCHANT_POLL_SECONDS", "1.5"))
        result_data = None; latency2 = 0
        for attempt in range(max_polls):
            if attempt:
                await asyncio.sleep(delay)
            data, lat = await request_json_async("GET", f"{BASE}/merchant/google/products/task_get/advanced/{task_id}",
                                                 auth=(username, password), timeout=timeout)
            latency2 += lat
            task = (data.get("tasks") or [{}])[0]
            if task.get("status_code") == 20000 and task.get("result"):
                result_data = task["result"][0]
                break
        if not result_data:
            return SourceResult("Google Shopping", "empty", error="DataForSEO Merchant Task noch nicht bereit; später erneut versuchen",
                                latency_ms=latency1 + latency2)
        items = result_data.get("items") or []
        records = []
        for rank, item in enumerate(items[:limit], 1):
            price = item.get("price") or {}
            records.append({
                "id": item.get("product_id") or item.get("title") or str(rank),
                "source": "Google Shopping", "kind": "price_offer", "title": item.get("title", ""),
                "description": item.get("description", ""), "rank": rank,
                "price": price.get("current") if isinstance(price, dict) else price,
                "currency": (price.get("currency") if isinstance(price, dict) else None) or "EUR",
                "seller": item.get("seller", "") or item.get("domain", ""),
                "domain": item.get("domain", ""), "rating": (item.get("rating") or {}).get("value") if isinstance(item.get("rating"), dict) else item.get("rating"),
                "reviews": (item.get("rating") or {}).get("votes_count") if isinstance(item.get("rating"), dict) else item.get("reviews"),
                "url": item.get("url", "") or item.get("product_url", ""),
                "product_id": item.get("product_id"), "data_docid": item.get("data_docid"),
                "date": item.get("date_posted", ""),
            })
        return SourceResult("Google Shopping", "ok" if records else "empty", records,
                            latency_ms=latency1 + latency2, total_available=len(records))
    except Exception as exc:
        return SourceResult("Google Shopping", "error", error=str(exc))


async def fetch_local_services(keyword: str, region: str = "DE", timeout: int = 30, limit: int = 50):
    username, password = _creds()
    location = os.getenv("DATAFORSEO_SERVICE_LOCATION_CODE")
    if not username or not password or not location:
        return SourceResult("Local Services", "disabled",
                            error="DATAFORSEO-Credentials und DATAFORSEO_SERVICE_LOCATION_CODE erforderlich")
    language = os.getenv("DATAFORSEO_LANGUAGE_CODE", "de")
    payload = [{"language_code": language, "location_code": int(location), "keyword": keyword,
                "depth": min(max(limit, 10), 100), "tag": "nischen-explorer"}]
    try:
        data, latency = await request_json_async("POST", f"{BASE}/serp/google/local_finder/live/advanced",
                                                 auth=(username, password), json=payload, timeout=timeout)
        task = (data.get("tasks") or [{}])[0]
        result = (task.get("result") or [{}])[0] if task.get("result") else {}
        items = result.get("items") or []
        records = []
        for rank, item in enumerate(items[:limit], 1):
            records.append({
                "id": item.get("place_id") or item.get("cid") or item.get("title") or str(rank),
                "source": "Local Services", "kind": "service", "title": item.get("title", ""),
                "description": item.get("description", ""), "rank": rank,
                "rating": (item.get("rating") or {}).get("value") if isinstance(item.get("rating"), dict) else None,
                "reviews": (item.get("rating") or {}).get("votes_count") if isinstance(item.get("rating"), dict) else None,
                "address": item.get("address", ""), "phone": item.get("phone", ""),
                "url": item.get("url", "") or item.get("website", ""), "domain": item.get("domain", ""),
            })
        return SourceResult("Local Services", "ok" if records else "empty", records,
                            latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("Local Services", "error", error=str(exc))
