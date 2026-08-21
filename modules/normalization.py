from .utils import stable_id
from .models import SourceResult, validate_records


def dedupe_records(records):
    seen = set(); out = []
    for raw in records or []:
        r = dict(raw)
        canonical_id = r.get("id") or stable_id(r.get("source", ""), r.get("url", ""), r.get("title", ""), r.get("text", ""))
        source = r.get("source", "")
        key = (source, canonical_id)
        if key in seen: continue
        seen.add(key); r["canonical_id"] = canonical_id; out.append(r)
    return out


def normalize_result(result: SourceResult) -> SourceResult:
    valid, invalid = validate_records(result.records)
    result.records = dedupe_records(valid)
    result.invalid_records = invalid
    result.valid_records = len(result.records)
    if result.status == "ok" and not result.records:
        result.status = "empty"
    return result


def merge_source_results(results):
    all_records = []
    for result in results:
        all_records.extend(result.records or [])
    return dedupe_records(all_records)


def source_summary(results):
    return [{"source": r.source, "status": r.status, "records": r.count, "total_available": r.total_available,
             "valid_records": r.valid_records, "invalid_records": r.invalid_records, "latency_ms": r.latency_ms,
             "error": r.error or "", "fetched_at": r.fetched_at, "cached": r.cached} for r in results]
