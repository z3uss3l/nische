"""Two-phase local-first refresh orchestrator.

Provider adapters are registered by the application. Dashboard code never invokes them.
A provider adapter returns a JSON-serializable normalized/raw snapshot.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

from .provider_policy import ProviderPolicy, CHANGE_PIPELINE, detect_change, may_fetch


@dataclass
class RefreshResult:
    provider: str
    status: str
    changed: bool=False
    content_hash: str=""
    queued: tuple[str,...]=()
    error: str=""


def refresh_provider(*, policy: ProviderPolicy, fetch: Callable[[],Any],
                     previous_hash: str|None, successful_fetch_dates: list[date],
                     today: date|None=None) -> RefreshResult:
    today=today or date.today()
    if not may_fetch(policy, successful_fetch_dates, today):
        return RefreshResult(policy.provider,"daily_limit")
    try:
        payload=fetch()
        snap, change=detect_change(policy.provider,payload,previous_hash)
        return RefreshResult(policy.provider,"ok",change.changed,snap.content_hash,
                             CHANGE_PIPELINE if change.changed else ())
    except Exception as exc:
        # Never convert transport/parser/access failure into an empty marketplace result.
        return RefreshResult(policy.provider,"error",error=f"{type(exc).__name__}: {exc}")


def run_refresh_batch(jobs: list[dict]) -> list[RefreshResult]:
    """Sequential by default: conservative for external providers and easy to audit."""
    return [refresh_provider(**job) for job in jobs]
