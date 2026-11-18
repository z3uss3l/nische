#!/usr/bin/env python3
"""Run configured local snapshot imports and durable change-processing.

Runs without remote requests by default. Non-configured handlers remain pending.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from modules.provider_registry import build_adapters
from modules.refresh_ledger import RefreshLedger
from modules.refresh_runtime import refresh,process_outbox
from modules.intelligence_store import upsert_signal,upsert_event


def normalize_snapshot(provider,payload):
    if not isinstance(payload,dict):
        raise ValueError("Snapshot must be an object with signals/events arrays")
    signals=payload.get("signals",[])
    events=payload.get("events",[])
    if not isinstance(signals,list) or not isinstance(events,list):
        raise ValueError("signals/events must be arrays")
    # Never silently reinterpret arbitrary marketplace JSON as canonical signals.
    for row in signals:
        if not isinstance(row,dict): raise ValueError("Signal must be an object")
        upsert_signal(row)
    for row in events:
        if not isinstance(row,dict): raise ValueError("Event must be an object")
        upsert_event(row)


def main():
    ledger=RefreshLedger()
    results=[refresh(adapter,ledger) for adapter in build_adapters()]
    outbox=process_outbox(ledger,{"normalize_snapshot":normalize_snapshot})
    print(json.dumps({"refresh":results,"outbox":outbox,"providers":ledger.provider_status()},
                     ensure_ascii=False,default=str))
    return 1 if any(r["status"]=="error" for r in results) or outbox["failed"] else 0


if __name__=="__main__":
    raise SystemExit(main())
