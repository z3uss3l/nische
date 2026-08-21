import math
from statistics import median

WEIGHTS = {"demand": .25, "pain": .25, "supply_gap": .20, "competition_gap": .15, "trend": .15}


def _clamp(v):
    return max(0.0, min(1.0, float(v)))


def _log_scale(v, ceiling):
    return _clamp(math.log1p(max(0.0, float(v))) / math.log1p(ceiling))


def calculate_gap_score(
    trends, reddit, books, social_mentions=None, keepa=None, seo_gaps=None,
    books_source_available=None, youtube=None, platform_trends=None,
    shopping=None, services=None, related_queries=None,
):
    trends, reddit, books = trends or [], reddit or [], books or []
    social_mentions, keepa, seo_gaps = social_mentions or [], keepa or [], seo_gaps or []
    youtube, platform_trends, shopping, services = youtube or [], platform_trends or [], shopping or [], services or []
    related_queries = related_queries or []

    # Demand: absolute search volume remains the strongest signal, but high-volume
    # video/social discovery can lift demand without pretending it is search volume.
    volumes = [float(x.get("search_volume") or 0) for x in seo_gaps]
    seo_demand = _log_scale(max(volumes), 100000) if volumes else None
    video_views = [float(x.get("views") or 0) for x in youtube]
    video_demand = _log_scale(max(video_views), 10_000_000) if video_views else None
    x_counts = [float(x.get("tweet_count") or 0) for x in platform_trends]
    x_demand = _log_scale(max(x_counts), 1_000_000) if x_counts else None
    pin_growth = [float(x.get("growth_mom") or 0) for x in platform_trends if x.get("platform") == "Pinterest"]
    pin_demand = _clamp(max(pin_growth) / 100.0) if pin_growth else None
    demand_signals = [x for x in (seo_demand, video_demand, x_demand, pin_demand) if x is not None]
    demand = _clamp(sum(demand_signals) / len(demand_signals)) if demand_signals else 0.0

    pain_signals = []
    for r in reddit + social_mentions:
        if r.get("intent") in {"complaint", "wish"}:
            engagement = math.log1p(max(0, r.get("score", 0)) + max(0, r.get("comments", 0)) * 2 + max(0, r.get("likes", 0)))
            pain_signals.append(min(1.0, .25 + engagement / 12) * float(r.get("intent_confidence", .5)))
    pain = _clamp(sum(pain_signals) / len(pain_signals)) if pain_signals else 0.0

    unique_titles = {str(b.get("title", "")).strip().lower() for b in books if b.get("title")}
    book_count = len(unique_titles)
    api_counts = [float(b.get("result_count")) for b in books if b.get("result_count") is not None]
    observed_supply = max(api_counts) if api_counts else float(book_count)
    if books_source_available is None:
        books_source_available = bool(books)
    supply_gap = 1.0 - _log_scale(observed_supply, 5000) if books_source_available else 0.0

    comps = [float(x.get("competition")) for x in seo_gaps if x.get("competition") is not None]
    seo_comp_gap = 1.0 - _clamp(sum(comps) / len(comps)) if comps else None
    seller_count = len({(x.get("seller") or x.get("domain") or "").lower() for x in shopping if x.get("seller") or x.get("domain")})
    shopping_gap = 1.0 - _log_scale(seller_count, 100) if shopping else None
    product_count = len({x.get("asin") for x in keepa if x.get("asin")})
    marketplace_gap = 1.0 - _log_scale(product_count, 1000) if keepa else None
    signals = [x for x in (seo_comp_gap, shopping_gap, marketplace_gap) if x is not None]
    competition_gap = _clamp(sum(signals) / len(signals)) if signals else 0.5

    ranks = [float(x.get("bsr")) for x in keepa if x.get("bsr") not in (None, "", 0)]
    market_traction = _clamp(1.0 - _log_scale(median(ranks), 500000)) if ranks else None

    trend_vals = [float(x.get("value", 0)) for x in trends]
    if len(trend_vals) >= 3:
        n = min(14, len(trend_vals)); recent = sum(trend_vals[-n:]) / n; prior = sum(trend_vals[:n]) / n
        level = _clamp(recent / 100); slope = _clamp((recent - prior) / 100)
        google_trend = _clamp(level * .55 + slope * .45)
    else:
        google_trend = None
    growth = [float(x.get("growth_mom") or 0) for x in platform_trends if x.get("growth_mom") is not None]
    platform_growth = _clamp(sum(growth) / len(growth) / 100.0) if growth else None
    rising = [float(x.get("value")) for x in related_queries if x.get("query_type") == "rising" and x.get("value") is not None]
    related_rising = _clamp(sum(rising) / len(rising) / 100.0) if rising else None
    trend_signals = [x for x in (google_trend, platform_growth, related_rising) if x is not None]
    trend = _clamp(sum(trend_signals) / len(trend_signals)) if trend_signals else 0.0

    weighted = sum([
        demand * WEIGHTS["demand"], pain * WEIGHTS["pain"], supply_gap * WEIGHTS["supply_gap"],
        competition_gap * WEIGHTS["competition_gap"], trend * WEIGHTS["trend"],
    ])
    score = 10 * weighted

    available = {
        "demand": bool(seo_gaps or youtube or platform_trends),
        "pain": bool(reddit or social_mentions),
        "supply": bool(books or shopping or keepa),
        "competition": bool(seo_gaps or shopping or keepa),
        "trend": bool(trends or platform_trends or related_queries),
    }
    confidence = sum(available.values()) / len(available)
    if confidence < .4:
        verdict = "Datenbasis zu dünn"
    elif score >= 7:
        verdict = "starke Opportunity"
    elif score >= 5:
        verdict = "prüfenswerte Opportunity"
    else:
        verdict = "schwache Opportunity"

    return {
        "score": round(score, 2), "confidence": round(confidence, 2), "verdict": verdict,
        "demand": round(demand, 3), "pain": round(pain, 3), "supply_gap": round(supply_gap, 3),
        "competition_gap": round(competition_gap, 3), "trend": round(trend, 3),
        "market_traction": round(market_traction, 3) if market_traction is not None else None,
        "book_count": book_count, "book_result_count": int(observed_supply) if observed_supply >= 0 else None,
        "reddit_posts": len(reddit), "social_mentions": len(social_mentions),
        "keyword_count": len(seo_gaps), "trend_points": len(trends), "keepa_products": product_count,
        "youtube_videos": len(youtube), "youtube_views": int(sum(video_views)) if video_views else 0,
        "platform_trends": len(platform_trends), "related_queries": len(related_queries), "rising_queries": len([x for x in related_queries if x.get("query_type") == "rising"]), "shopping_offers": len(shopping),
        "shopping_sellers": seller_count, "service_results": len(services),
        "weights": WEIGHTS, "available_signals": available,
    }
