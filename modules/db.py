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
