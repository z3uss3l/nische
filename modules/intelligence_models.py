"""Canonical domain models for Nische v5 market intelligence.

These models deliberately separate observations, events, relationships and inferred
market impacts. A correlation or LLM hypothesis is never stored as an observed fact.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceLevel(str, Enum):
    observed = "observed"
    official = "official"
    derived = "derived"
    statistical = "statistical"
    plausible = "plausible"
    speculative = "speculative"


class AuthorityLevel(str, Enum):
    binding = "binding"
    adopted_not_effective = "adopted_not_effective"
    legislative_proposal = "legislative_proposal"
    consultation = "consultation"
    official_roadmap = "official_roadmap"
    standard_draft = "standard_draft"
    committee_work_item = "committee_work_item"
    authority_announcement = "authority_announcement"
    industry_position = "industry_position"
    none = "none"


class TemporalSignal(BaseModel):
    model_config = ConfigDict(extra="allow")
    signal_id: str
    timestamp: datetime
    source: str
    domain: str
    metric: str
    value: float
    unit: str = ""
    region: str = "DE"
    subject: str = ""
    baseline: float | None = None
    deviation: float | None = None
    percentile: float | None = Field(default=None, ge=0, le=1)
    change_1d: float | None = None
    change_7d: float | None = None
    change_30d: float | None = None
    evidence: EvidenceLevel = EvidenceLevel.observed
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    event_id: str
    source: str
    domain: str
    event_type: str
    title: str
    known_since: datetime
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    effective_at: datetime | None = None
    region: str = "DE"
    authority: str = ""
    authority_level: AuthorityLevel = AuthorityLevel.none
    status: str = ""
    url: str = ""
    evidence: EvidenceLevel = EvidenceLevel.observed
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    relationship_id: str
    source_node: str
    target_node: str
    relation: str
    direction: Literal[-1, 0, 1] = 0
    lag_days: float | None = None
    strength: float | None = None
    sample_size: int = 0
    stability: float | None = Field(default=None, ge=0, le=1)
    mechanism: str = ""
    evidence: EvidenceLevel = EvidenceLevel.plausible
    confidence: float = Field(default=0.0, ge=0, le=1)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    geography: str = ""
    seasonality: str = ""
    sources: list[str] = Field(default_factory=list)


class ProductNode(BaseModel):
    node_id: str
    name: str
    node_type: Literal["product", "component", "material", "substance", "service", "classification"]
    identifiers: dict[str, str] = Field(default_factory=dict)
    classifications: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductEdge(BaseModel):
    parent_id: str
    child_id: str
    relation: Literal["contains", "uses", "classified_as", "substitutes", "depends_on", "affected_by"]
    quantity: float | None = None
    unit: str = ""
    evidence: EvidenceLevel = EvidenceLevel.observed
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: str = ""


class FundingOpportunity(BaseModel):
    opportunity_id: str
    source: str
    title: str
    programme: str = ""
    funder: str = ""
    geography: list[str] = Field(default_factory=list)
    opens_at: datetime | None = None
    deadline: datetime | None = None
    budget_total: float | None = None
    budget_call: float | None = None
    max_grant: float | None = None
    funding_rate: float | None = None
    currency: str = "EUR"
    eligibility: list[str] = Field(default_factory=list)
    consortium_required: bool | None = None
    url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketImpact(BaseModel):
    impact_id: str
    subject: str
    region: str
    horizon_days: int
    direction: Literal[-1, 0, 1]
    impact_type: str
    magnitude: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    inferred_at: datetime


class OpportunityScore(BaseModel):
    subject: str
    base_opportunity: float = Field(ge=0, le=10)
    dynamic_impact: float = Field(ge=-5, le=5)
    forward_impact: float = Field(ge=-5, le=5)
    confidence: float = Field(ge=0, le=1)
    as_of: datetime
    drivers: list[MarketImpact] = Field(default_factory=list)
