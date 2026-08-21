import logging
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text, Index, event, select
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

Base = declarative_base()

class Analysis(Base):
    __tablename__ = "analysis"
    id = Column(Integer, primary_key=True)
    keyword = Column(String(300), nullable=False, index=True)
    region = Column(String(10), nullable=False)
    days = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    score = Column(Float)
    confidence = Column(Float)
    details = Column(JSON)
    source_snapshot = Column(JSON)
    __table_args__ = (Index("ix_analysis_keyword_timestamp", "keyword", "timestamp"),)

class TrendRecord(Base):
    __tablename__ = "trend_records"
    canonical_id = Column(String(64), primary_key=True)
    source = Column(String(80), primary_key=True)
    kind = Column(String(40), nullable=False, index=True)
    title = Column(Text, default="")
    url = Column(Text, default="")
    date = Column(String(64), default="")
    score = Column(Float)
    payload = Column(JSON)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    __table_args__ = (Index("ix_trend_source_kind_last_seen", "source", "kind", "last_seen"),)


class SourceHealth(Base):
    __tablename__ = "source_health"
    source = Column(String(80), primary_key=True)
    enabled = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="unknown")
    last_checked_at = Column(DateTime, index=True)
    last_fetched_at = Column(DateTime, index=True)
    last_error = Column(Text, default="")
    latency_ms = Column(Integer)


class DashboardPreference(Base):
    __tablename__ = "dashboard_preferences"
    id = Column(Integer, primary_key=True, default=1)
    visible_sections = Column(JSON, nullable=False, default=list)
    categories = Column(JSON, nullable=False, default=list)
    attributes = Column(JSON, nullable=False, default=list)
    theme = Column(String(40), nullable=False, default="night")

_ENGINE = None
logger = logging.getLogger(__name__)

def get_db_engine():
    global _ENGINE
    if _ENGINE is not None: return _ENGINE
    url = os.getenv("DATABASE_URL", "sqlite:///./nischen_explorer.db")
    kwargs = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    _ENGINE = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(_ENGINE, "connect")
        def _sqlite_pragmas(dbapi_connection, connection_record):
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()
    Base.metadata.create_all(_ENGINE)
    return _ENGINE

def init_db():
    get_db_engine()


def get_dashboard_preferences(default_sections):
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session.begin() as session:
        row = session.get(DashboardPreference, 1)
        if row is None:
            row = DashboardPreference(id=1, visible_sections=list(default_sections))
            session.add(row)
        return {"visible_sections": row.visible_sections or list(default_sections),
                "categories": row.categories or [], "attributes": row.attributes or [],
                "theme": row.theme or "night"}


def save_dashboard_preferences(visible_sections, categories, attributes, theme):
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session.begin() as session:
        row = session.get(DashboardPreference, 1)
        if row is None:
            row = DashboardPreference(id=1)
            session.add(row)
        row.visible_sections = list(visible_sections)
        row.categories = list(categories)
        row.attributes = list(attributes)
        row.theme = theme


def ensure_sources(sources):
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session.begin() as session:
        for source in sources:
            if session.get(SourceHealth, source) is None:
                session.add(SourceHealth(source=source))


def list_source_health(sources=None):
    if sources:
        ensure_sources(sources)
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session() as session:
        rows = session.execute(select(SourceHealth).order_by(SourceHealth.source)).scalars().all()
        return [{
            "source": row.source,
            "enabled": bool(row.enabled),
            "status": row.status,
            "last_checked_at": row.last_checked_at,
            "last_fetched_at": row.last_fetched_at,
            "last_error": row.last_error or "",
            "latency_ms": row.latency_ms,
        } for row in rows]


def set_source_enabled(source, enabled):
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session.begin() as session:
        row = session.get(SourceHealth, source)
        if row is None:
            row = SourceHealth(source=source)
            session.add(row)
        row.enabled = int(bool(enabled))
        if not enabled:
            row.status = "disabled"
        elif row.status == "disabled":
            row.status = "unknown"


def disabled_sources():
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session() as session:
        return {row.source for row in session.execute(
            select(SourceHealth).where(SourceHealth.enabled == 0)
        ).scalars()}


def record_source_result(result):
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)
    fetched_at = None
    if result.status in {"ok", "empty"} and result.fetched_at:
        fetched_at = datetime.fromisoformat(result.fetched_at)
    with Session.begin() as session:
        row = session.get(SourceHealth, result.source)
        if row is None:
            row = SourceHealth(source=result.source)
            session.add(row)
        row.status = result.status
        row.last_checked_at = now
        if fetched_at is not None:
            row.last_fetched_at = fetched_at
        row.last_error = result.error or ""
        row.latency_ms = result.latency_ms

def save_analysis(keyword, region, days, score, source_snapshot, records=None):
    engine = get_db_engine(); Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with Session.begin() as session:
            session.add(Analysis(keyword=keyword, region=region, days=days, score=(score or {}).get("score"),
                                 confidence=(score or {}).get("confidence"), details=score or {}, source_snapshot=source_snapshot))
            now = datetime.now(timezone.utc)
            for r in records or []:
                cid, source = str(r.get("canonical_id") or r.get("id") or ""), str(r.get("source") or "unknown")
                if not cid: continue
                existing = session.get(TrendRecord, (cid, source))
                if existing:
                    existing.kind = r.get("kind", existing.kind); existing.title = r.get("title", existing.title) or ""
                    existing.url = r.get("url", existing.url) or ""; existing.date = r.get("date", existing.date) or ""
                    existing.score = r.get("score", existing.score); existing.payload = r; existing.last_seen = now
                else:
                    session.add(TrendRecord(canonical_id=cid, source=source, kind=r.get("kind", "unknown"),
                                            title=r.get("title", "") or "", url=r.get("url", "") or "", date=r.get("date", "") or "",
                                            score=r.get("score"), payload=r, first_seen=now, last_seen=now))
        return True
    except Exception:
        logger.exception("Analyse konnte nicht in der Datenbank gespeichert werden")
        return False

def recent_history(keyword, limit=30):
    engine = get_db_engine(); Session = sessionmaker(bind=engine)
    with Session() as session:
        rows = session.execute(select(Analysis).where(Analysis.keyword == keyword).order_by(Analysis.timestamp.desc()).limit(limit)).scalars().all()
        return [{"id": r.id, "keyword": r.keyword, "region": r.region, "days": r.days, "timestamp": r.timestamp,
                 "score": r.score, "confidence": r.confidence} for r in reversed(rows)]
