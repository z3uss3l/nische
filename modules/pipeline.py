import asyncio
from .models import SourceResult
from . import news_fetcher, reddit_fetcher, books_fetcher, trends_fetcher, social_listener, dataforseo_fetcher, keepa_fetcher, scorer
from . import async_sources
from . import social_trends_fetcher, youtube_fetcher, commerce_fetcher, web_sources
from .normalization import consistency_report, merge_source_results, normalize_result
from . import db


SOURCE_NAMES = (
    "GDELT", "Hacker News", "GNews", "TheNewsAPI", "Reddit", "X", "Octolens", "XPOZ",
    "SnitchFeed", "OpenLibrary", "Google Books", "Google Trends",
    "Google Trends Related", "Google Trends Regions", "DataForSEO", "Keepa",
    "YouTube", "X Trends", "Instagram Hashtags", "Pinterest Trends",
    "Facebook Pages", "Google Shopping", "Local Services", "Configured Feeds",
    "Configured URLs", "Web Crawler",
)


def _sync(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try: return loop.run_until_complete(coro)
        finally: loop.close()

async def _run(keyword, region="DE", days=30, max_workers=8):
    jobs = [
        async_sources.fetch_gdelt(keyword, days),
        async_sources.fetch_hacker_news(keyword, days),
        async_sources.fetch_gnews(keyword, days),
        async_sources.fetch_thenews(keyword, days),
        asyncio.to_thread(reddit_fetcher.fetch_reddit_pain_points, keyword, days),
        async_sources.fetch_x(keyword, min(days, 7)),
        async_sources.fetch_connector("Octolens", keyword, days),
        async_sources.fetch_connector("XPOZ", keyword, days),
        async_sources.fetch_connector("SnitchFeed", keyword, days),
        async_sources.fetch_books_openlibrary(keyword),
        async_sources.fetch_books_google(keyword),
        asyncio.to_thread(trends_fetcher.fetch_trends, keyword, region, max(days, 30)),
        asyncio.to_thread(trends_fetcher.fetch_related_queries, keyword, region),
        asyncio.to_thread(trends_fetcher.fetch_interest_by_region, keyword, region),
        async_sources.fetch_dataforseo(keyword),
        async_sources.fetch_keepa(keyword),
        youtube_fetcher.fetch_youtube(keyword, region, days),
        social_trends_fetcher.fetch_x_trends(region),
        social_trends_fetcher.fetch_instagram_hashtag(keyword),
        social_trends_fetcher.fetch_pinterest_trends(region),
        social_trends_fetcher.fetch_facebook_pages(keyword),
        commerce_fetcher.fetch_google_shopping(keyword, region),
        commerce_fetcher.fetch_local_services(keyword, region),
        web_sources.fetch_configured_feeds(keyword),
        web_sources.fetch_configured_urls(keyword),
        web_sources.crawl_configured_sites(keyword),
    ]
    disabled = db.disabled_sources()
    jobs = [job for name, job in zip(SOURCE_NAMES, jobs) if name not in disabled]
    active_names = [name for name in SOURCE_NAMES if name not in disabled]
    semaphore = asyncio.Semaphore(max(1, max_workers))
    async def guarded(job):
        async with semaphore:
            return await job
    raw = await asyncio.gather(*(guarded(job) for job in jobs), return_exceptions=True)
    results = []
    for name, value in zip(active_names, raw):
        if isinstance(value, Exception): value = SourceResult(name, "error", error=str(value))
        elif not isinstance(value, SourceResult): value = SourceResult(name, "ok", value or [])
        result = normalize_result(value)
        db.record_source_result(result)
        results.append(result)
    for name in disabled:
        if name in SOURCE_NAMES:
            results.append(SourceResult(name, "disabled", error="In Quellenpflege deaktiviert"))
    results.sort(key=lambda r: r.source)
    by_source = {r.source: r for r in results}
    empty = lambda n: by_source.get(n, SourceResult(n, "empty"))
    trends = empty("Google Trends").records; related_queries = empty("Google Trends Related").records; reddit = empty("Reddit").records
    books = empty("OpenLibrary").records + empty("Google Books").records
    social = sum((empty(n).records for n in ("X","Octolens","XPOZ","SnitchFeed","Instagram Hashtags","Facebook Pages")), [])
    keepa, seo = empty("Keepa").records, empty("DataForSEO").records
    youtube = empty("YouTube").records
    platform_trends = empty("X Trends").records + empty("Pinterest Trends").records
    shopping = empty("Google Shopping").records
    services = empty("Local Services").records
    books_source_available = any(empty(n).status in {"ok", "empty"} for n in ("OpenLibrary", "Google Books"))
    score = scorer.calculate_gap_score(
        trends, reddit, books, social, keepa, seo,
        books_source_available=books_source_available, youtube=youtube,
        platform_trends=platform_trends, shopping=shopping, services=services, related_queries=related_queries,
    )
    records = merge_source_results(results)
    return {"results": results, "records": records, "score": score,
            "consistency": consistency_report(keyword, records)}

def run_analysis(keyword, region="DE", days=30, max_workers=8):
    return _sync(_run(keyword, region, days, max_workers))
