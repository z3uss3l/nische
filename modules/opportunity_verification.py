"""Generic opportunity verification contracts and deterministic gap logic.

Marketplace/network adapters only collect observations. This module decides what
those observations mean, making Dashboard, workers and future MCP use identical logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from statistics import median
from typing import Any, Iterable


class ProbeStatus(str, Enum):
    OK="ok"; ZERO="zero"; ERROR="error"; BLOCKED="blocked"; UNKNOWN="unknown"


class GapKind(str, Enum):
    CONFIRMED_ZERO="confirmed_zero"
    NEAR_ZERO="near_zero"
    SEMANTIC_GAP="semantic_gap"
    AVAILABILITY_GAP="availability_gap"
    GEOGRAPHIC_GAP="geographic_gap"
    PRICE_GAP="price_gap"
    QUALITY_GAP="quality_gap"
    FORMAT_GAP="format_gap"
    VARIANT_GAP="variant_gap"
    NONE="none"
    DATA_UNKNOWN="data_unknown"


class ValidationState(str, Enum):
    DISCOVERED="discovered"; PROBING="probing"; CONTINUE="continue"
    PIVOT="pivot"; WATCH="watch"; KILL="kill"; BLOCKED="blocked"


@dataclass
class Candidate:
    candidate_id: str
    subject: str
    lens: str = "generic"
    region: str = "DE"
    candidate_type: str = "market"
    demand_evidence: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProbeStep:
    step_id: str
    provider: str
    mode: str
    query: str
    region: str = "DE"
    category: str = ""
    identifiers: dict[str, str] = field(default_factory=dict)
    required: bool = True


@dataclass
class ProbePlan:
    candidate_id: str
    steps: list[ProbeStep]
    strategy: str = "query_ladder_v1"


@dataclass
class ProbeResult:
    step_id: str
    provider: str
    query: str
    status: ProbeStatus
    result_count: int | None = None
    relevant_count: int | None = None
    available_count: int | None = None
    prices: list[float] = field(default_factory=list)
    median_rating: float | None = None
    median_reviews: float | None = None
    relevance: float | None = None
    error: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GapEvidence:
    kind: GapKind
    confidence: float
    rationale: list[str]
    providers: list[str]
    observations: int
    metrics: dict[str, Any] = field(default_factory=dict)


QUERY_LADDER = ("identifier", "exact", "synonym", "semantic", "category", "substitute")


def build_query_ladder(candidate: Candidate, providers: Iterable[str], *,
                       identifiers: dict[str, str] | None = None,
                       synonyms: Iterable[str] = (), substitutes: Iterable[str] = ()) -> ProbePlan:
    """Build reproducible broadening searches; adapters decide provider-specific syntax."""
    identifiers = identifiers or {}
    steps: list[ProbeStep] = []
    for provider in providers:
        if identifiers:
            for key, value in identifiers.items():
                if value:
                    steps.append(ProbeStep(f"{provider}:identifier:{key}", provider, "identifier", value,
                                           candidate.region, identifiers={key:value}))
        steps.append(ProbeStep(f"{provider}:exact", provider, "exact", candidate.subject, candidate.region))
        for i, q in enumerate(synonyms):
            steps.append(ProbeStep(f"{provider}:synonym:{i}", provider, "synonym", q, candidate.region))
        steps.append(ProbeStep(f"{provider}:semantic", provider, "semantic", candidate.subject, candidate.region))
        for i, q in enumerate(substitutes):
            steps.append(ProbeStep(f"{provider}:substitute:{i}", provider, "substitute", q, candidate.region, required=False))
    return ProbePlan(candidate.candidate_id, steps)


def classify_gap(results: Iterable[ProbeResult], *, near_zero_threshold: int = 3,
                 min_independent_providers: int = 2) -> GapEvidence:
    """Classify negative supply evidence without converting technical failure into demand."""
    rows = list(results)
    valid = [r for r in rows if r.status in {ProbeStatus.OK, ProbeStatus.ZERO}]
    providers = sorted({r.provider for r in valid})
    if not valid:
        return GapEvidence(GapKind.DATA_UNKNOWN, 0.0, ["Keine valide Marketplace-Beobachtung."], [], len(rows))

    exactish = [r for r in valid if ":exact" in r.step_id or ":identifier:" in r.step_id]
    broad = [r for r in valid if any(f":{m}" in r.step_id for m in ("synonym","semantic"))]
    exact_relevant = sum((r.relevant_count if r.relevant_count is not None else r.result_count or 0) for r in exactish)
    broad_relevant = sum((r.relevant_count if r.relevant_count is not None else r.result_count or 0) for r in broad)
    available = sum(r.available_count or 0 for r in valid)
    prices = [p for r in valid for p in r.prices if p is not None and p >= 0]
    confidence = min(0.95, 0.35 + 0.18 * len(providers) + 0.03 * min(len(valid), 8))
    if len(providers) < min_independent_providers:
        confidence *= 0.72

    why=[]
    if exact_relevant == 0 and broad_relevant == 0 and len(providers) >= min_independent_providers:
        why.append(f"Keine relevanten Treffer über {len(providers)} unabhängige Anbieter nach Query-Broadening.")
        return GapEvidence(GapKind.CONFIRMED_ZERO, confidence, why, providers, len(valid),
                           {"exact_relevant":0,"broad_relevant":0})
    if exact_relevant == 0 and broad_relevant > 0:
        why.append("Exakte Nachfrageformulierung ohne Treffer; breitere/semantische Suche findet Alternativen.")
        return GapEvidence(GapKind.SEMANTIC_GAP, confidence, why, providers, len(valid),
                           {"exact_relevant":0,"broad_relevant":broad_relevant})
    total_relevant = exact_relevant + broad_relevant
    if total_relevant <= near_zero_threshold:
        why.append(f"Nur {total_relevant} relevante Angebote in der Prüfkaskade.")
        return GapEvidence(GapKind.NEAR_ZERO, confidence, why, providers, len(valid),
                           {"relevant":total_relevant})
    if total_relevant > 0 and available == 0 and any(r.available_count is not None for r in valid):
        why.append("Angebote gefunden, aber kein beobachtetes Angebot verfügbar.")
        return GapEvidence(GapKind.AVAILABILITY_GAP, confidence, why, providers, len(valid),
                           {"relevant":total_relevant,"available":0})
    return GapEvidence(GapKind.NONE, confidence, ["Aus den Probes ergibt sich keine belastbare Angebotslücke."],
                       providers, len(valid), {"relevant":total_relevant,
                       "median_price": median(prices) if prices else None})


def unmet_demand_evidence(*, demand_strength: float, demand_acceleration: float,
                          gap: GapEvidence, independent_demand_sources: int,
                          ambiguity: float=0.0, saturation: float=0.0) -> dict[str, float]:
    """Transparent bounded evidence score. It ranks candidates; it is not a sales forecast."""
    ds=max(0.0,min(1.0,demand_strength)); da=max(0.0,min(1.0,demand_acceleration))
    agreement=min(1.0, independent_demand_sources/4)
    gap_strength = 0.0 if gap.kind in {GapKind.NONE, GapKind.DATA_UNKNOWN} else gap.confidence
    penalty=max(0.0,min(1.0,0.55*ambiguity+0.45*saturation))
    raw=(0.35*ds+0.20*da+0.15*agreement+0.30*gap_strength)*(1-0.65*penalty)
    confidence=min(1.0, 0.5*gap.confidence+0.5*agreement)
    return {"score":round(100*raw,2),"confidence":round(confidence,3)}
