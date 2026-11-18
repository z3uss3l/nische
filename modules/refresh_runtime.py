"""Local-first refresh runner with durable quotas and explicit task handlers."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from typing import Any,Callable
from .provider_policy import ProviderPolicy
from .refresh_ledger import RefreshLedger


@dataclass(frozen=True)
class ProviderAdapter:
    policy: ProviderPolicy
    fetch: Callable[[],Any]


def refresh(adapter:ProviderAdapter,ledger:RefreshLedger)->dict:
    p=adapter.policy
    reservation=ledger.reserve(p.provider,p.max_fetches_per_day)
    if reservation is None:
        return {"provider":p.provider,"status":"daily_limit","changed":False}
    try:
        payload=adapter.fetch()
        if payload is None:
            raise ValueError("Provider returned None, not a valid empty snapshot")
        changed,fingerprint=ledger.commit_snapshot(p.provider,payload)
        ledger.complete(reservation,"ok")
        return {"provider":p.provider,"status":"ok","changed":changed,"hash":fingerprint}
    except Exception as exc:
        ledger.complete(reservation,"error",f"{type(exc).__name__}: {exc}")
        return {"provider":p.provider,"status":"error","changed":False,"error":str(exc)}


def process_outbox(ledger:RefreshLedger,handlers:dict[str,Callable[[str,dict],None]],limit:int=100)->dict:
    """Only execute registered real handlers; unknown tasks remain pending, never falsely marked done."""
    done=0; failed=0; unhandled=[]
    for job in ledger.pending_jobs(limit):
        handler=handlers.get(job["task"])
        if handler is None:
            unhandled.append(job["task"])
            continue
        snapshot=ledger.latest(job["provider"])
        if snapshot is None or snapshot["hash"]!=job["content_hash"]:
            # Obsolete job, superseded by a newer snapshot.
            ledger.finish_job(job["id"])
            done+=1
            continue
        try:
            handler(job["provider"],snapshot["payload"])
            ledger.finish_job(job["id"])
            done+=1
        except Exception as exc:
            ledger.finish_job(job["id"],f"{type(exc).__name__}: {exc}")
            failed+=1
    return {"done":done,"failed":failed,"unhandled":sorted(set(unhandled))}
