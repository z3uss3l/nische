"""Local-first provider policy and change-trigger primitives."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, timezone
from enum import Enum
import hashlib, json
from typing import Any


class AccessMode(str, Enum):
    LOCAL="local"
    PUBLIC_BULK="public_bulk"
    PUBLIC_FEED="public_feed"
    PUBLIC_API="public_api"
    PROVIDER_ANONYMOUS="provider_anonymous"
    AUTHENTICATED_API="authenticated_api"
    WEB_FETCH="web_fetch"


@dataclass(frozen=True)
class ProviderPolicy:
    provider: str
    access_mode: AccessMode
    max_fetches_per_day: int = 2
    preferred_hours_local: tuple[int,...] = (5,12)
    dashboard_live_fetch: bool = False
    conditional_requests: bool = True
    respects_robots_and_terms: bool = True
    requires_key: bool = False


@dataclass(frozen=True)
class SnapshotFingerprint:
    provider: str
    fetched_at: datetime
    content_hash: str
    etag: str=""
    last_modified: str=""
    row_count: int|None=None


@dataclass(frozen=True)
class ChangeSet:
    changed: bool
    old_hash: str|None
    new_hash: str
    reason: str


DEFAULT_WEB_POLICY = ProviderPolicy("generic_web", AccessMode.WEB_FETCH)


def canonical_hash(payload: Any) -> str:
    raw=json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def detect_change(provider: str, payload: Any, previous_hash: str|None=None, *,
                  etag: str="", last_modified: str="", row_count: int|None=None):
    new_hash=canonical_hash(payload)
    snap=SnapshotFingerprint(provider, datetime.now(timezone.utc), new_hash, etag, last_modified, row_count)
    if previous_hash is None:
        return snap, ChangeSet(True,None,new_hash,"initial_snapshot")
    if previous_hash == new_hash:
        return snap, ChangeSet(False,previous_hash,new_hash,"unchanged")
    return snap, ChangeSet(True,previous_hash,new_hash,"content_changed")


def may_fetch(policy: ProviderPolicy, successful_fetch_dates: list[date], today: date) -> bool:
    """Hard daily ceiling. Caller may additionally enforce robots/terms and backoff."""
    used=sum(1 for d in successful_fetch_dates if d == today)
    return used < policy.max_fetches_per_day


# Side effects to enqueue after a changed provider snapshot. Workers implement these names.
CHANGE_PIPELINE=(
    "normalize_snapshot",
    "recompute_temporal_features",
    "refresh_candidate_evidence",
    "reclassify_gaps",
    "recompute_market_states",
    "refresh_relationship_candidates",
    "refresh_collisions",
    "reprioritize_probe_queue",
    "invalidate_dashboard_cache",
)
