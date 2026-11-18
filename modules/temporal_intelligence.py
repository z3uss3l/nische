"""Pure temporal feature and market-impact primitives.

No network access here. Keeping derivation deterministic makes historical backtests
reproducible and prevents source adapters from embedding business conclusions.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import sqrt
from statistics import mean, pstdev
from typing import Iterable

from .intelligence_models import TemporalSignal


def enrich_signal(current: TemporalSignal, history: Iterable[TemporalSignal]) -> TemporalSignal:
    """Attach simple point-in-time features using only observations known at current.timestamp."""
    prior = sorted(
        (x for x in history
         if x.metric == current.metric and x.region == current.region
         and x.subject == current.subject and x.timestamp < current.timestamp),
        key=lambda x: x.timestamp,
    )
    if not prior:
        return current

    def nearest(days: int):
        target = current.timestamp.timestamp() - days * 86400
        return min(prior, key=lambda x: abs(x.timestamp.timestamp() - target))

    updates = {}
    for days, field in ((1, "change_1d"), (7, "change_7d"), (30, "change_30d")):
        old = nearest(days)
        if old.value:
            updates[field] = (current.value - old.value) / abs(old.value)

    vals = [x.value for x in prior]
    if vals:
        updates["baseline"] = mean(vals)
        updates["deviation"] = current.value - updates["baseline"]
        updates["percentile"] = sum(v <= current.value for v in vals) / len(vals)

    return current.model_copy(update=updates)


def lagged_correlation(
    x: list[TemporalSignal], y: list[TemporalSignal], max_lag_days: int = 30
) -> list[dict]:
    """Daily Pearson correlations for candidate discovery, not causal proof."""
    xd = {s.timestamp.date(): s.value for s in x}
    yd = {s.timestamp.date(): s.value for s in y}
    out = []
    for lag in range(-max_lag_days, max_lag_days + 1):
        pairs = []
        for day, xv in xd.items():
            shifted = day.fromordinal(day.toordinal() + lag)
            if shifted in yd:
                pairs.append((xv, yd[shifted]))
        if len(pairs) < 5:
            continue
        xs, ys = zip(*pairs)
        mx, my = mean(xs), mean(ys)
        num = sum((a - mx) * (b - my) for a, b in pairs)
        den = sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
        out.append({"lag_days": lag, "correlation": num / den if den else 0.0, "sample_size": len(pairs)})
    return out


def collision_summary(drivers: list[dict]) -> dict:
    """Summarise independent signed drivers without claiming causality."""
    usable = [d for d in drivers if d.get("confidence", 0) > 0 and d.get("magnitude", 0) >= 0]
    if not usable:
        return {"dynamic_impact": 0.0, "confidence": 0.0, "domains": []}
    by_domain = defaultdict(list)
    for d in usable:
        by_domain[d.get("domain", "unknown")].append(d)
    domain_scores = []
    confidences = []
    for domain, items in by_domain.items():
        weighted = sum(float(i.get("direction", 0)) * float(i.get("magnitude", 0)) * float(i.get("confidence", 0)) for i in items)
        weight = sum(float(i.get("confidence", 0)) for i in items)
        domain_scores.append(weighted / weight if weight else 0.0)
        confidences.append(max(float(i.get("confidence", 0)) for i in items))
    raw = mean(domain_scores)
    # Multiple independent domains can strengthen confidence, not create unbounded magnitude.
    confidence = min(1.0, mean(confidences) * (1 + min(len(by_domain) - 1, 4) * 0.08))
    return {
        "dynamic_impact": round(max(-5.0, min(5.0, raw * 5)), 3),
        "confidence": round(confidence, 3),
        "domains": sorted(by_domain),
    }
