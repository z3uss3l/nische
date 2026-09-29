"""Germany-first market intelligence sources.

Official/public sources are preferred. Every adapter returns SourceResult and fails
explicitly instead of converting transport errors into zero demand.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote
import re

from .http import request_json_async
from .models import SourceResult


async def fetch_govdata(keyword: str, region: str = "DE", rows: int = 40):
    """Discover German public datasets through GovData's CKAN API."""
    keyword = (keyword or "").strip()
    if not keyword:
        return SourceResult("GovData", "empty")
    try:
        payload, latency = await request_json_async(
            "GET",
            "https://www.govdata.de/ckan/api/3/action/package_search",
            params={"q": keyword, "rows": max(1, min(rows, 100)), "sort": "metadata_modified desc"},
            timeout=20,
        )
        result = payload.get("result") or {}
        records = []
        for item in result.get("results") or []:
            title = item.get("title") or item.get("name") or ""
            notes = re.sub(r"<[^>]+>", " ", item.get("notes") or "")
            records.append({
                "id": item.get("id") or item.get("name") or title,
                "source": "GovData",
                "kind": "public_dataset",
                "title": title,
                "text": re.sub(r"\s+", " ", notes).strip()[:2000],
                "url": f"https://www.govdata.de/suche/daten/{item.get('name')}" if item.get("name") else "",
                "date": item.get("metadata_modified") or item.get("metadata_created") or "",
                "region": region,
                "publisher": ((item.get("organization") or {}).get("title") or ""),
                "tags": [t.get("display_name") or t.get("name") for t in item.get("tags") or []],
            })
        return SourceResult("GovData", "ok" if records else "empty", records,
                            latency_ms=latency, total_available=int(result.get("count") or len(records)))
    except Exception as exc:
        return SourceResult("GovData", "error", error=str(exc))


async def fetch_ted_procurement(keyword: str, region: str = "DE", limit: int = 50):
    """Keyword-matched public procurement notices via the anonymous TED Search API v3.

    Germany is selected by place of performance when region=DE. TED expert-query
    syntax can evolve; failures remain visible as source errors.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return SourceResult("TED Ausschreibungen", "empty")
    # Full-text term plus German place-of-performance filter.
    safe = keyword.replace('"', ' ').strip()
    query = f'FT~"{safe}" AND CY=DE' if (region or "DE").upper() == "DE" else f'FT~"{safe}"'
    body = {
        "query": query,
        "fields": [
            "publication-number", "notice-title", "buyer-name", "publication-date",
            "deadline-receipt-tender-date-lot", "place-of-performance", "classification-cpv"
        ],
        "page": 1,
        "limit": max(1, min(limit, 100)),
        "scope": "ACTIVE",
        "checkQuerySyntax": True,
        "paginationMode": "PAGE_NUMBER",
    }
    try:
        payload, latency = await request_json_async(
            "POST", "https://api.ted.europa.eu/v3/notices/search", json=body, timeout=25
        )
        notices = payload.get("notices") or payload.get("results") or []
        records = []
        for item in notices:
            pub = item.get("publication-number") or item.get("publicationNumber") or item.get("notice-id") or ""
            title = item.get("notice-title") or item.get("noticeTitle") or item.get("title") or ""
            if isinstance(title, dict):
                title = title.get("deu") or title.get("de") or next(iter(title.values()), "")
            buyer = item.get("buyer-name") or item.get("buyerName") or ""
            if isinstance(buyer, dict):
                buyer = buyer.get("deu") or buyer.get("de") or next(iter(buyer.values()), "")
            records.append({
                "id": str(pub or title),
                "source": "TED Ausschreibungen",
                "kind": "procurement",
                "title": str(title),
                "buyer": buyer,
                "date": item.get("publication-date") or item.get("publicationDate") or "",
                "deadline": item.get("deadline-receipt-tender-date-lot") or "",
                "cpv": item.get("classification-cpv") or "",
                "region": region,
                "url": f"https://ted.europa.eu/de/notice/-/detail/{quote(str(pub))}" if pub else "",
            })
        total = payload.get("totalNoticeCount") or payload.get("total") or len(records)
        return SourceResult("TED Ausschreibungen", "ok" if records else "empty", records,
                            latency_ms=latency, total_available=int(total or 0))
    except Exception as exc:
        return SourceResult("TED Ausschreibungen", "error", error=str(exc))


async def fetch_ba_labour_market(region: str = "DE"):
    """Official BA labour-market context.

    The public API currently exposes regional aggregate vacancy tables, not arbitrary
    keyword search. Therefore these records are context only and MUST NOT be treated
    as keyword-specific demand.
    """
    region = (region or "DE").upper()
    endpoint = "https://statistik-dr.arbeitsagentur.de/bifrontend/bids-api/pc/v1/tableFetch/dia/EckwerteTabelleSTEA"
    params = {"sort": "desc"}
    # Current UI uses country codes. DE is exact; unsupported subregions deliberately
    # fall back to Germany instead of pretending a code is an official BA region name.
    try:
        payload, latency = await request_json_async("GET", endpoint, params=params, timeout=25)
        rows = payload if isinstance(payload, list) else (
            payload.get("data") or payload.get("rows") or payload.get("result") or []
        )
        if isinstance(rows, dict):
            rows = rows.get("data") or rows.get("rows") or []
        records = []
        for idx, row in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(row, dict):
                continue
            records.append({
                "id": str(row.get("id") or row.get("Berichtsmonat") or idx),
                "source": "BA Arbeitsmarkt",
                "kind": "labour_market_context",
                "title": "Gemeldete Arbeitsstellen – amtlicher Kontext",
                "date": str(row.get("Berichtsmonat") or row.get("Monat") or ""),
                "region": "DE",
                "metrics": row,
                "url": "https://statistik.arbeitsagentur.de/DE/Navigation/Service/API/API-Start-Nav.html",
            })
        return SourceResult("BA Arbeitsmarkt", "ok" if records else "empty", records,
                            latency_ms=latency, total_available=len(records))
    except Exception as exc:
        return SourceResult("BA Arbeitsmarkt", "error", error=str(exc))
