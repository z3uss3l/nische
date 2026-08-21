"""Backward-compatible sync entry point for the current Keepa implementation."""
from .models import SourceResult


def fetch_keepa(keyword, timeout=30):
    # The active pipeline uses the async implementation. Keeping this wrapper
    # prevents stale callers from silently using the former /search payload parser.
    from .pipeline import _sync
    from .async_sources import fetch_keepa as fetch_keepa_async
    return _sync(fetch_keepa_async(keyword, timeout=timeout))
