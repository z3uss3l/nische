"""Filter/view model for the v5 dashboard."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any


DEFAULT_PANELS = ["Situation", "Kalender", "Timeline", "Trends", "Heatmap", "Evidenz"]

BUILTIN_VIEWS = {
    "Allgemeine Marktlage": {"query": "", "regions": [], "domains": [], "evidence": [], "panels": DEFAULT_PANELS},
    "Finanzdienstleistungen": {"query": "finanz bank kredit versicherung investment", "regions": ["DE"],
        "domains": ["finance", "macro", "regulation", "funding", "news"], "evidence": [], "panels": DEFAULT_PANELS},
    "T-Shirt / Printmotive": {"query": "t-shirt shirt print motiv design apparel merch",
        "regions": ["DE"], "domains": ["demand", "social", "commerce", "events", "calendar"], "evidence": [],
        "panels": ["Situation", "Kalender", "Trends", "Heatmap", "Evidenz"]},
    "Marketplace-Warenangebot": {"query": "", "regions": ["DE"],
        "domains": ["commerce", "demand", "supply", "prices", "logistics", "calendar"], "evidence": [],
        "panels": DEFAULT_PANELS},
    "E-Book / Publishing": {"query": "ebook buch publishing kindle lesen",
        "regions": ["DE"], "domains": ["demand", "social", "books", "commerce", "calendar", "events"], "evidence": [],
        "panels": ["Situation", "Kalender", "Trends", "Heatmap", "Evidenz"]},
}


def _text(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(k, "")) for k in ("title", "subject", "metric", "event_type", "domain", "source")).lower()


def filter_records(records, *, query="", regions=None, domains=None, evidence=None,
                   start: date | None = None, end: date | None = None):
    terms = [x.lower() for x in query.split() if x.strip()]
    regions, domains, evidence = set(regions or []), set(domains or []), set(evidence or [])
    out = []
    for r in records:
        if regions and r.get("region") not in regions: continue
        if domains and r.get("domain") not in domains: continue
        if evidence and r.get("evidence") not in evidence: continue
        if terms and not any(t in _text(r) for t in terms): continue
        raw_dt = r.get("timestamp") or r.get("starts_at") or r.get("effective_at") or r.get("known_since")
        if raw_dt:
            dt = raw_dt if isinstance(raw_dt, datetime) else datetime.fromisoformat(str(raw_dt).replace("Z", "+00:00"))
            d = dt.date()
            if start and d < start: continue
            if end and d > end: continue
        out.append(r)
    return out


def derive_calendar_context(day: date) -> list[dict]:
    """Deterministic context only; regional holidays/ferien are supplied by source adapters."""
    out = [
        {"event_id": f"calendar:{day}:weekday", "known_since": datetime.combine(day, time.min),
         "starts_at": datetime.combine(day, time.min), "source": "Calendar Engine", "domain": "calendar",
         "event_type": "weekday", "title": day.strftime("%A"), "region": "DE", "evidence": "derived",
         "confidence": 1.0}
    ]
    if day.day <= 3:
        out.append({"event_id": f"calendar:{day}:month_start", "known_since": datetime.combine(day, time.min),
                    "starts_at": datetime.combine(day, time.min), "source": "Calendar Engine", "domain": "calendar",
                    "event_type": "month_start", "title": "Monatsanfang", "region": "DE",
                    "evidence": "derived", "confidence": 1.0})
    if day.day >= 27:
        out.append({"event_id": f"calendar:{day}:month_end", "known_since": datetime.combine(day, time.min),
                    "starts_at": datetime.combine(day, time.min), "source": "Calendar Engine", "domain": "calendar",
                    "event_type": "month_end", "title": "Monatsende", "region": "DE",
                    "evidence": "derived", "confidence": 1.0})
    return out
