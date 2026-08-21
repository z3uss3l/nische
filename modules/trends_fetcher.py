from datetime import datetime, timedelta
from .models import SourceResult


def _client():
    from pytrends.request import TrendReq
    return TrendReq(hl="de", tz=120, timeout=(10, 30), retries=1, backoff_factor=0.5)


def fetch_trends(keyword, region="DE", days=90):
    try:
        pytrends = _client()
        end = datetime.now()
        start = end - timedelta(days=max(days, 7))
        timeframe = f"{start.strftime('%Y-%m-%d')} {end.strftime('%Y-%m-%d')}"
        pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo=region, gprop="")
        data = pytrends.interest_over_time()
        if data.empty or keyword not in data.columns:
            return SourceResult("Google Trends", "empty")
        data = data.reset_index()
        records = [{"id": row["date"].isoformat(), "source": "Google Trends", "kind": "trend",
                     "date": row["date"].strftime("%Y-%m-%d"), "value": int(row[keyword])} for _, row in data.iterrows()]
        return SourceResult("Google Trends", "ok", records, total_available=len(records))
    except Exception as exc:
        return SourceResult("Google Trends", "error", error=str(exc))


def fetch_related_queries(keyword, region="DE"):
    """Google Trends related queries: top queries and rising queries.

    These are discovery signals, not absolute search-volume measurements.
    """
    try:
        pytrends = _client()
        pytrends.build_payload([keyword], timeframe="today 3-m", geo=region, gprop="")
        related = pytrends.related_queries() or {}
        bucket = related.get(keyword) or {}
        records = []
        for query_type in ("rising", "top"):
            frame = bucket.get(query_type)
            if frame is None or getattr(frame, "empty", True):
                continue
            for idx, row in frame.iterrows():
                query = str(row.get("query") or "").strip()
                if not query:
                    continue
                raw_value = row.get("value")
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    value = None
                records.append({
                    "id": f"{query_type}:{query}",
                    "source": "Google Trends Related",
                    "kind": "related_query",
                    "title": query,
                    "keyword": query,
                    "query_type": query_type,
                    "value": value,
                    "region": region,
                    "url": f"https://www.google.com/search?q={query.replace(' ', '+')}",
                })
        return SourceResult("Google Trends Related", "ok" if records else "empty", records, total_available=len(records))
    except Exception as exc:
        return SourceResult("Google Trends Related", "error", error=str(exc))


def fetch_interest_by_region(keyword, region="DE"):
    """Interest by country/region for contextual geographic comparison."""
    try:
        pytrends = _client()
        pytrends.build_payload([keyword], timeframe="today 3-m", geo=region, gprop="")
        data = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True, inc_geo_code=True)
        if data is None or data.empty:
            return SourceResult("Google Trends Regions", "empty")
        data = data.reset_index()
        value_col = keyword if keyword in data.columns else data.columns[1]
        records = []
        for _, row in data.iterrows():
            value = row.get(value_col)
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            region_name = str(row.get("geoName") or row.iloc[0])
            records.append({
                "id": f"{region}:{region_name}",
                "source": "Google Trends Regions",
                "kind": "regional_interest",
                "title": region_name,
                "region": region_name,
                "value": value,
                "parent_region": region,
            })
        return SourceResult("Google Trends Regions", "ok" if records else "empty", records, total_available=len(records))
    except Exception as exc:
        return SourceResult("Google Trends Regions", "error", error=str(exc))
