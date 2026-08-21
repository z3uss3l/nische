import os
from .http import request_json
from .models import SourceResult
from .utils import safe_float


def fetch_keyword_gaps(keyword, location_code=None, language_code=None, limit=100, timeout=30):
    username, password = os.getenv("DATAFORSEO_USERNAME"), os.getenv("DATAFORSEO_PASSWORD")
    if not username or not password:
        return SourceResult("DataForSEO", "disabled", error="DATAFORSEO_USERNAME/DATAFORSEO_PASSWORD fehlen")
    location_code = int(location_code or os.getenv("DATAFORSEO_LOCATION_CODE", "2276"))
    language_code = language_code or os.getenv("DATAFORSEO_LANGUAGE_CODE", "de")
    url = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
    payload = [{
        "keywords": [keyword], "location_code": location_code, "language_code": language_code,
        "include_serp_info": True, "limit": min(limit, 1000),
        "order_by": ["keyword_info.search_volume,desc"],
    }]
    try:
        data, latency = request_json("POST", url, auth=(username, password), json=payload, timeout=timeout)
        tasks = data.get("tasks") or []
        if not tasks:
            return SourceResult("DataForSEO", "empty", latency_ms=latency)
        result = (tasks[0].get("result") or [{}])[0]
        records = []
        for item in result.get("items", []):
            ki = item.get("keyword_info") or {}
            si = item.get("serp_info") or {}
            records.append({
                "id": item.get("keyword"), "source": "DataForSEO", "kind": "keyword",
                "keyword": item.get("keyword", ""), "search_volume": ki.get("search_volume", 0),
                "competition": ki.get("competition", 0), "cpc": ki.get("cpc", 0),
                "trend": ki.get("monthly_searches", []), "keyword_difficulty": si.get("keyword_difficulty"),
                "serp_results": si.get("se_results_count"),
            })
        return SourceResult("DataForSEO", "ok" if records else "empty", records, latency_ms=latency,
                            total_available=len(records))
    except Exception as exc:
        return SourceResult("DataForSEO", "error", error=str(exc))
