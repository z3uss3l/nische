"""Regression tests for persistent quota and outbox behavior."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from modules.refresh_ledger import RefreshLedger
from modules.refresh_runtime import ProviderAdapter, refresh, process_outbox
from modules.provider_policy import ProviderPolicy, AccessMode


def test_atomic_quota_across_workers(tmp_path):
    path=str(tmp_path/"ledger.sqlite3")
    ledger=RefreshLedger(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations=list(pool.map(lambda _: RefreshLedger(path).reserve("example",2),range(16)))
    assert sum(x is not None for x in reservations)==2


def test_failures_consume_budget(tmp_path):
    ledger=RefreshLedger(str(tmp_path/"ledger.sqlite3"))
    def bad(): raise TimeoutError("unreachable")
    adapter=ProviderAdapter(ProviderPolicy("test",AccessMode.WEB_FETCH),bad)
    assert refresh(adapter,ledger)["status"]=="error"
    assert refresh(adapter,ledger)["status"]=="error"
    assert refresh(adapter,ledger)["status"]=="daily_limit"


def test_changed_snapshots_queue_only_once(tmp_path):
    ledger=RefreshLedger(str(tmp_path/"ledger.sqlite3"))
    changed,h=ledger.commit_snapshot("test",{"data":[1,2]})
    assert changed
    count=len(ledger.pending_jobs())
    assert count>0
    changed2,h2=ledger.commit_snapshot("test",{"data":[1,2]})
    assert not changed2 and h==h2
    assert len(ledger.pending_jobs())==count


def test_unimplemented_handlers_not_acknowledged(tmp_path):
    ledger=RefreshLedger(str(tmp_path/"ledger.sqlite3"))
    ledger.commit_snapshot("test",{"x":1})
    result=process_outbox(ledger,{})
    assert result["done"]==0
    assert len(ledger.pending_jobs())>0


def test_registered_handler_receives_actual_snapshot(tmp_path):
    ledger=RefreshLedger(str(tmp_path/"ledger.sqlite3"))
    ledger.commit_snapshot("test",{"x":1})
    seen=[]
    result=process_outbox(ledger,{"normalize_snapshot":lambda provider,payload:seen.append((provider,payload))})
    assert result["done"]==1
    assert seen==[("test",{"x":1})]
