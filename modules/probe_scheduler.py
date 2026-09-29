"""Priority policy for background opportunity verification.

The scheduler is deliberately provider-agnostic. Provider adapters execute ProbeStep
objects and write ProbeResult observations; this policy only decides what deserves work.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class QueueDecision:
    priority: float
    cadence_hours: int
    reason: tuple[str,...]


def prioritize(*, demand_strength: float=0, acceleration: float=0, anomaly: float=0,
               gap_confidence: float=0, external_trigger: float=0, uncertainty: float=0,
               probe_cost: float=0) -> QueueDecision:
    vals=[max(0.0,min(1.0,x)) for x in
          (demand_strength,acceleration,anomaly,gap_confidence,external_trigger,uncertainty,probe_cost)]
    demand_strength,acceleration,anomaly,gap_confidence,external_trigger,uncertainty,probe_cost=vals
    # Uncertainty raises information value, but expensive probes are penalized.
    p=(.24*demand_strength+.18*acceleration+.16*anomaly+.20*gap_confidence+
       .10*external_trigger+.12*uncertainty) * (1-.45*probe_cost)
    priority=round(100*p,2)
    cadence=6 if priority>=75 else 24 if priority>=50 else 72 if priority>=25 else 168
    reasons=[]
    for label,value in (("Nachfrage",demand_strength),("Beschleunigung",acceleration),("Anomalie",anomaly),
                        ("Gap-Evidenz",gap_confidence),("externer Trigger",external_trigger),
                        ("Informationswert",uncertainty)):
        if value>=.6: reasons.append(label)
    return QueueDecision(priority,cadence,tuple(reasons) or ("Routineprüfung",))


def due(last_checked: datetime | None, decision: QueueDecision, now: datetime | None=None) -> bool:
    now=now or datetime.now(timezone.utc)
    if last_checked is None: return True
    if last_checked.tzinfo is None: last_checked=last_checked.replace(tzinfo=timezone.utc)
    return now-last_checked >= timedelta(hours=decision.cadence_hours)
