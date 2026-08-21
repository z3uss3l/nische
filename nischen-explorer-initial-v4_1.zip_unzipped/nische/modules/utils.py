import os
import re
import hashlib
from dotenv import load_dotenv


def load_env():
    load_dotenv(override=False)


def get_config():
    return {key: os.getenv(key) for key in [
        "REDDIT_CLIENT_ID", "REDDIT_SECRET", "REDDIT_USER_AGENT",
        "GNEWS_API_KEY", "THENEWS_API_KEY", "GOOGLE_BOOKS_API_KEY", "X_BEARER_TOKEN",
        "YOUTUBE_API_KEY", "META_ACCESS_TOKEN", "INSTAGRAM_BUSINESS_USER_ID", "FACEBOOK_PAGE_IDS",
        "META_GRAPH_VERSION", "PINTEREST_ACCESS_TOKEN", "PINTEREST_REGION",
        "DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD", "DATAFORSEO_LOCATION_CODE",
        "DATAFORSEO_LANGUAGE_CODE", "DATAFORSEO_SHOPPING_LOCATION_CODE", "DATAFORSEO_SHOPPING_LANGUAGE_CODE",
        "DATAFORSEO_SERVICE_LOCATION_CODE", "DATAFORSEO_MERCHANT_MAX_POLLS", "DATAFORSEO_MERCHANT_POLL_SECONDS",
        "KEEPA_API_KEY", "KEEPA_DOMAIN", "KEEPA_MAX_RESULTS",
        "OCTOLENS_API_KEY", "OCTOLENS_ENDPOINT", "XPOZ_API_KEY", "XPOZ_ENDPOINT",
        "SNITCHFEED_API_KEY", "SNITCHFEED_ENDPOINT", "FEED_URLS", "URL_REQUESTS", "CRAWL_URLS",
        "CRAWL_MAX_PAGES", "CRAWL_MAX_DEPTH", "CRAWL_USER_AGENT", "DATABASE_URL",
        "CACHE_TTL_SECONDS", "HTTP_TIMEOUT_SECONDS", "MAX_WORKERS"
    ]}


def normalize_keyword(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value[:200]


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return value or "analysis"


def stable_id(*parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
