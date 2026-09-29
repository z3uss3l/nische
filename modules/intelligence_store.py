"""Persistence and query layer for v5 intelligence.

Kept separate from legacy db.py so the prototype can evolve without breaking v4.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .db import get_db_engine


class V5Base(DeclarativeBase):
    pass


class SignalRow(V5Base):
    __tablename__ = "temporal_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    domain: Mapped[str] = mapped_column(String(80), index=True)
    metric: Mapped[str] = mapped_column(String(120), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40), default="")
    region: Mapped[str] = mapped_column(String(40), index=True, default="DE")
    subject: Mapped[str] = mapped_column(String(300), index=True, default="")
    evidence: Mapped[str] = mapped_column(String(40), index=True, default="observed")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (Index("ix_v5_signal_domain_region_time", "domain", "region", "timestamp"),)


class EventRow(V5Base):
    __tablename__ = "temporal_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    known_since: Mapped[datetime] = mapped_column(DateTime, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    domain: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(40), index=True, default="DE")
    authority_level: Mapped[str] = mapped_column(String(60), index=True, default="none")
    evidence: Mapped[str] = mapped_column(String(40), index=True, default="observed")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    url: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (Index("ix_v5_event_domain_region_start", "domain", "region", "starts_at"),)


class SavedViewRow(V5Base):
    __tablename__ = "saved_views_v5"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_v5():
    V5Base.metadata.create_all(get_db_engine())


def _session():
    init_v5()
    return sessionmaker(bind=get_db_engine(), expire_on_commit=False)


def upsert_signal(signal: dict[str, Any]):
    Session = _session()
    with Session.begin() as s:
        row = s.scalar(select(SignalRow).where(SignalRow.signal_id == signal["signal_id"]))
        values = {
            "timestamp": signal["timestamp"], "source": signal["source"], "domain": signal["domain"],
            "metric": signal["metric"], "value": signal["value"], "unit": signal.get("unit", ""),
            "region": signal.get("region", "DE"), "subject": signal.get("subject", ""),
            "evidence": signal.get("evidence", "observed"), "confidence": signal.get("confidence", 1.0),
            "payload": signal,
        }
        if row:
            for k, v in values.items(): setattr(row, k, v)
        else:
            s.add(SignalRow(signal_id=signal["signal_id"], **values))


def upsert_event(event: dict[str, Any]):
    Session = _session()
    with Session.begin() as s:
        row = s.scalar(select(EventRow).where(EventRow.event_id == event["event_id"]))
        values = {
            "known_since": event["known_since"], "starts_at": event.get("starts_at"),
            "ends_at": event.get("ends_at"), "effective_at": event.get("effective_at"),
            "source": event["source"], "domain": event["domain"], "event_type": event["event_type"],
            "title": event["title"], "region": event.get("region", "DE"),
            "authority_level": event.get("authority_level", "none"), "evidence": event.get("evidence", "observed"),
            "confidence": event.get("confidence", 1.0), "url": event.get("url", ""), "payload": event,
        }
        if row:
            for k, v in values.items(): setattr(row, k, v)
        else:
            s.add(EventRow(event_id=event["event_id"], **values))


def list_signals(limit=5000):
    Session = _session()
    with Session() as s:
        rows = s.scalars(select(SignalRow).order_by(SignalRow.timestamp.desc()).limit(limit)).all()
        return [dict(r.payload or {}, signal_id=r.signal_id, timestamp=r.timestamp, source=r.source,
                     domain=r.domain, metric=r.metric, value=r.value, unit=r.unit, region=r.region,
                     subject=r.subject, evidence=r.evidence, confidence=r.confidence) for r in rows]


def list_events(limit=5000):
    Session = _session()
    with Session() as s:
        rows = s.scalars(select(EventRow).order_by(EventRow.starts_at.desc()).limit(limit)).all()
        return [dict(r.payload or {}, event_id=r.event_id, known_since=r.known_since, starts_at=r.starts_at,
                     ends_at=r.ends_at, effective_at=r.effective_at, source=r.source, domain=r.domain,
                     event_type=r.event_type, title=r.title, region=r.region, authority_level=r.authority_level,
                     evidence=r.evidence, confidence=r.confidence, url=r.url) for r in rows]


def list_saved_views():
    Session = _session()
    with Session() as s:
        return {r.name: r.config or {} for r in s.scalars(select(SavedViewRow).order_by(SavedViewRow.name)).all()}


def save_view(name: str, config: dict[str, Any]):
    name = (name or "").strip()[:160]
    if not name: raise ValueError("Ansichtsname fehlt")
    Session = _session()
    with Session.begin() as s:
        row = s.scalar(select(SavedViewRow).where(SavedViewRow.name == name))
        if row:
            row.config = config; row.updated_at = datetime.now(timezone.utc)
        else:
            s.add(SavedViewRow(name=name, config=config))


def delete_view(name: str):
    Session = _session()
    with Session.begin() as s:
        s.execute(delete(SavedViewRow).where(SavedViewRow.name == name))
