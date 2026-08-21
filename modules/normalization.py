import re
from collections import defaultdict

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


def consistency_report(keyword, records):
    terms = {term for term in re.findall(r"[\w-]+", (keyword or "").casefold()) if len(term) > 2}
    matches = 0
    identity_groups = defaultdict(list)
    missing_fields = 0
    for record in records or []:
        searchable = " ".join(str(record.get(field, "")) for field in ("title", "text", "keyword", "description")).casefold()
        if terms and all(term in searchable for term in terms):
            matches += 1
        if not record.get("source") or not record.get("kind") or not (record.get("canonical_id") or record.get("id")):
            missing_fields += 1
        identity = (record.get("url") or "").strip().casefold() or (record.get("title") or "").strip().casefold()
        if identity:
            identity_groups[identity].append(record.get("source") or "unknown")
    duplicate_groups = [sources for sources in identity_groups.values() if len(sources) > 1]
    return {
        "keyword": keyword,
        "records": len(records or []),
        "keyword_matches": matches,
        "keyword_match_rate": round(matches / len(records), 3) if records else 0.0,
        "duplicate_groups": duplicate_groups,
        "duplicate_count": sum(len(group) - 1 for group in duplicate_groups),
        "missing_required_fields": missing_fields,
        "consistent": not missing_fields,
    }


def source_summary(results):
    return [{"source": r.source, "status": r.status, "records": r.count, "total_available": r.total_available,
             "valid_records": r.valid_records, "invalid_records": r.invalid_records, "latency_ms": r.latency_ms,
             "error": r.error or "", "fetched_at": r.fetched_at, "cached": r.cached} for r in results]
