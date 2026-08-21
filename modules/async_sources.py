"""Async HTTP fetch layer. Sync SDKs (PRAW/pytrends) stay isolated in to_thread()."""
from datetime import datetime, timedelta, timezone
import os
import asyncio
from .http import request_json_async, gather_limited
from .models import SourceResult


def _cutoff(days):
    return datetime.now(timezone.utc) - timedelta(days=days)

async def fetch_gdelt(keyword, days=7, timeout=15):
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {"query": keyword, "format": "json", "timespan": f"{days}d", "maxrecords": 100, "sort": "HybridRel"}
    try:
        data, latency = await request_json_async("GET", url, params=params, timeout=timeout)
        records = [{"id": a.get("url") or a.get("title"), "source": "GDELT", "kind": "news",
                    "title": a.get("title", "").strip(), "source_name": a.get("domain") or a.get("source", ""),
                    "date": a.get("seendate", ""), "url": a.get("url", ""), "language": a.get("language", ""),
                    "country": a.get("sourcecountry", ""), "snippet": ""} for a in data.get("articles", [])]
        return SourceResult("GDELT", "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("GDELT", "error", error=str(exc))

async def fetch_gnews(keyword, days=7, language="de", country="de", timeout=15):
    key = os.getenv("GNEWS_API_KEY")
    if not key: return SourceResult("GNews", "disabled", error="GNEWS_API_KEY fehlt")
    try:
        data, latency = await request_json_async("GET", "https://gnews.io/api/v4/search", params={
            "q": keyword, "token": key, "lang": language, "country": country, "max": 100,
            "from": _cutoff(days).isoformat()}, timeout=timeout)
        records = [{"id": a.get("url") or a.get("title"), "source": "GNews", "kind": "news",
                    "title": a.get("title", "").strip(), "source_name": (a.get("source") or {}).get("name", ""),
                    "date": a.get("publishedAt", ""), "url": a.get("url", ""), "language": language,
                    "country": country, "snippet": a.get("description", "") or ""} for a in data.get("articles", [])]
        return SourceResult("GNews", "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("GNews", "error", error=str(exc))

async def fetch_thenews(keyword, days=7, language="de", timeout=15):
    key = os.getenv("THENEWS_API_KEY")
    if not key: return SourceResult("TheNewsAPI", "disabled", error="THENEWS_API_KEY fehlt")
    try:
        data, latency = await request_json_async("GET", "https://api.thenewsapi.com/v1/news/all", params={
            "api_token": key, "search": keyword, "language": language, "limit": 50,
            "published_after": _cutoff(days).strftime("%Y-%m-%dT%H:%M:%SZ")}, timeout=timeout)
        records = [{"id": a.get("uuid") or a.get("url"), "source": "TheNewsAPI", "kind": "news",
                    "title": a.get("title", "").strip(), "source_name": a.get("source", ""),
                    "date": a.get("published_at", ""), "url": a.get("url", ""), "language": a.get("language", language),
                    "country": "", "snippet": a.get("snippet", "") or a.get("description", "") or ""} for a in data.get("data", [])]
        return SourceResult("TheNewsAPI", "ok" if records else "empty", records, latency_ms=latency,
                            total_available=(data.get("meta") or {}).get("found"))
    except Exception as exc:
        return SourceResult("TheNewsAPI", "error", error=str(exc))

async def fetch_x(keyword, days=7, limit=100, timeout=20):
    bearer = os.getenv("X_BEARER_TOKEN")
    if not bearer: return SourceResult("X", "disabled", error="X_BEARER_TOKEN fehlt")
    start = datetime.now(timezone.utc) - timedelta(days=min(days, 7))
    try:
        data, latency = await request_json_async("GET", "https://api.x.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {bearer}"}, params={"query": f'({keyword}) -is:retweet',
            "max_results": min(max(limit, 10), 100), "start_time": start.isoformat().replace("+00:00", "Z"),
            "tweet.fields": "created_at,public_metrics,lang,author_id"}, timeout=timeout)
        records = []
        for t in data.get("data", []):
            m = t.get("public_metrics") or {}
            records.append({"id": t.get("id"), "source": "X", "kind": "social", "text": t.get("text", ""),
                            "date": t.get("created_at", ""), "likes": m.get("like_count", 0),
                            "reposts": m.get("retweet_count", 0), "replies": m.get("reply_count", 0),
                            "lang": t.get("lang", ""), "url": f"https://x.com/i/web/status/{t.get('id')}"})
        return SourceResult("X", "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("X", "error", error=str(exc))

async def fetch_books_openlibrary(keyword, limit=100, timeout=15):
    try:
        data, latency = await request_json_async("GET", "https://openlibrary.org/search.json", params={
            "q": keyword, "limit": min(limit, 100), "fields": "key,title,author_name,first_publish_year,edition_count,ratings_average,subject,number_of_pages_median"}, timeout=timeout)
        records = [{"id": d.get("key") or d.get("title"), "source": "OpenLibrary", "kind": "book",
                    "title": d.get("title", ""), "author": ", ".join(d.get("author_name", [])[:3]),
                    "year": d.get("first_publish_year"), "edition_count": d.get("edition_count", 0),
                    "rating": d.get("ratings_average"), "subjects": ", ".join(d.get("subject", [])[:8]),
                    "pages": d.get("number_of_pages_median"), "result_count": data.get("numFound"), "url": f"https://openlibrary.org{d.get('key', '')}" if d.get("key") else ""}
                   for d in data.get("docs", [])]
        return SourceResult("OpenLibrary", "ok" if records else "empty", records, latency_ms=latency, total_available=data.get("numFound"))
    except Exception as exc:
        return SourceResult("OpenLibrary", "error", error=str(exc))

async def fetch_books_google(keyword, limit=40, timeout=15):
    params = {"q": keyword, "maxResults": min(limit, 40), "orderBy": "relevance", "printType": "books", "projection": "lite"}
    if os.getenv("GOOGLE_BOOKS_API_KEY"): params["key"] = os.getenv("GOOGLE_BOOKS_API_KEY")
    try:
        data, latency = await request_json_async("GET", "https://www.googleapis.com/books/v1/volumes", params=params, timeout=timeout)
        records = []
        for item in data.get("items", []):
            v = item.get("volumeInfo", {})
            records.append({"id": item.get("id"), "source": "Google Books", "kind": "book", "title": v.get("title", ""),
                            "author": ", ".join(v.get("authors", [])[:3]), "year": (v.get("publishedDate") or "")[:4],
                            "rating": v.get("averageRating"), "rating_count": v.get("ratingsCount", 0),
                            "subjects": ", ".join(v.get("categories", [])[:8]), "pages": v.get("pageCount"), "result_count": data.get("totalItems"), "url": v.get("infoLink", "") })
        return SourceResult("Google Books", "ok" if records else "empty", records, latency_ms=latency, total_available=data.get("totalItems"))
    except Exception as exc:
        return SourceResult("Google Books", "error", error=str(exc))

async def fetch_dataforseo(keyword, timeout=30, limit=100):
    username, password = os.getenv("DATAFORSEO_USERNAME"), os.getenv("DATAFORSEO_PASSWORD")
    if not username or not password:
        return SourceResult("DataForSEO", "disabled", error="DATAFORSEO_USERNAME/DATAFORSEO_PASSWORD fehlen")
    try:
        payload = [{"keywords": [keyword], "location_code": int(os.getenv("DATAFORSEO_LOCATION_CODE", "2276")),
                    "language_code": os.getenv("DATAFORSEO_LANGUAGE_CODE", "de"), "include_serp_info": True,
                    "limit": min(limit, 1000), "order_by": ["keyword_info.search_volume,desc"]}]
        data, latency = await request_json_async("POST", "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live",
                                                 auth=(username, password), json=payload, timeout=timeout)
        tasks = data.get("tasks") or []
        task = tasks[0] if tasks else {}
        result = (task.get("result") or [{}])[0] if task.get("result") else {}
        records = []
        for item in result.get("items", []):
            ki, si = item.get("keyword_info") or {}, item.get("serp_info") or {}
            records.append({"id": item.get("keyword"), "source": "DataForSEO", "kind": "keyword", "keyword": item.get("keyword", ""),
                            "search_volume": ki.get("search_volume", 0), "competition": ki.get("competition", 0),
                            "cpc": ki.get("cpc", 0), "trend": ki.get("monthly_searches", []),
                            "keyword_difficulty": si.get("keyword_difficulty"), "serp_results": si.get("se_results_count")})
        if not tasks: return SourceResult("DataForSEO", "empty", latency_ms=latency)
        return SourceResult("DataForSEO", "ok" if records else "empty", records, latency_ms=latency, total_available=task.get("result_count", len(records)))
    except Exception as exc:
        return SourceResult("DataForSEO", "error", error=str(exc))

async def _keepa_product(key, domain, asin, timeout):
    return await request_json_async("GET", "https://api.keepa.com/product", params={"key": key, "domain": domain, "asin": asin}, timeout=timeout)

async def fetch_keepa(keyword, timeout=30, limit=20):
    key = os.getenv("KEEPA_API_KEY")
    if not key: return SourceResult("Keepa", "disabled", error="KEEPA_API_KEY fehlt")
    domain = int(os.getenv("KEEPA_DOMAIN", "3"))
    limit = min(int(os.getenv("KEEPA_MAX_RESULTS", str(limit))), 100)
    started = asyncio.get_running_loop().time()
    try:
        search, _ = await request_json_async("GET", "https://api.keepa.com/search", params={
            "key": key, "domain": domain, "type": "product", "term": keyword, "page": 0}, timeout=timeout)
        asins = search.get("asinList") or search.get("products") or []
        asins = [x if isinstance(x, str) else x.get("asin") for x in asins]
        asins = [x for x in asins if x][:limit]
        if not asins:
            return SourceResult("Keepa", "empty", latency_ms=int((asyncio.get_running_loop().time()-started)*1000), total_available=0)
        # Keepa explicitly supports parallel requests; each product request is one token.
        responses = await gather_limited((_keepa_product(key, domain, asin, timeout) for asin in asins), limit=6)
        records = []
        failures = 0
        for response in responses:
            if isinstance(response, Exception):
                failures += 1; continue
            data, _ = response
            for p in data.get("products", []) or []:
                asin = p.get("asin", "")
                current = p.get("current") or []
                # Keepa prices are in the marketplace's smallest currency unit.
                price_cents = current[0] if current and isinstance(current[0], (int, float)) else None
                if price_cents is not None and price_cents < 0: price_cents = None
                ranks = p.get("salesRanks") or {}
                bsr_values = [v for v in ranks.values() if isinstance(v, (int, float)) and v > 0]
                bsr = min(bsr_values) if bsr_values else None
                records.append({"id": asin, "source": "Keepa", "kind": "product", "asin": asin,
                                "title": p.get("title", ""), "bsr": bsr, "price": (price_cents / 100) if price_cents is not None else None,
                                "price_minor": price_cents, "currency": "EUR" if domain == 3 else "marketplace",
                                "category": p.get("categoryName", ""), "url": f"https://www.amazon.de/dp/{asin}" if asin else "",
                                "keepa_domain": domain, "tokens_left": data.get("tokensLeft")})
        status = "ok" if records else ("error" if failures and not records else "empty")
        err = f"{failures} Produktabfragen fehlgeschlagen" if failures else None
        return SourceResult("Keepa", status, records, error=err, latency_ms=int((asyncio.get_running_loop().time()-started)*1000), total_available=len(asins))
    except Exception as exc:
        return SourceResult("Keepa", "error", error=str(exc))

async def fetch_connector(name, keyword, days=7, timeout=20):
    endpoint, api_key = os.getenv(f"{name.upper()}_ENDPOINT"), os.getenv(f"{name.upper()}_API_KEY")
    if not endpoint or not api_key:
        return SourceResult(name, "disabled", error=f"{name.upper()}_ENDPOINT und API-Key nicht konfiguriert")
    try:
        data, latency = await request_json_async("GET", endpoint, headers={"Authorization": f"Bearer {api_key}"},
            params={"q": keyword, "query": keyword, "days": days}, timeout=timeout)
        items = data.get("results") or data.get("items") or data.get("mentions") or []
        records = [{"id": str(i.get("id") or i.get("url") or i.get("text", ""))[:200], "source": name, "kind": "social",
                    "text": i.get("text", ""), "platform": i.get("platform") or i.get("source", ""),
                    "sentiment": i.get("sentiment", "neutral"), "intent": i.get("intent", "other"),
                    "date": i.get("date") or i.get("created_at", ""), "url": i.get("url", "")} for i in items if isinstance(i, dict)]
        return SourceResult(name, "ok" if records else "empty", records, latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult(name, "error", error=str(exc))
