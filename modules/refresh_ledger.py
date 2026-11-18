"""Durable, process-safe provider quota, snapshot and change outbox.

SQLite WAL and BEGIN IMMEDIATE serialize reservations across independent workers.
A reservation counts even on failed requests: no unlimited retry loophole.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

from .provider_policy import canonical_hash, CHANGE_PIPELINE

TZ=ZoneInfo("Europe/Berlin")


class RefreshLedger:
    def __init__(self, path: str | None = None):
        self.path=path or os.environ.get("NISCHE_REFRESH_DB","data/refresh_ledger.sqlite3")
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS fetch_attempts(
              id INTEGER PRIMARY KEY, provider TEXT NOT NULL, day TEXT NOT NULL,
              started_at TEXT NOT NULL, status TEXT NOT NULL,
              error TEXT, UNIQUE(id));
            CREATE INDEX IF NOT EXISTS ix_fetch_day ON fetch_attempts(provider,day);
            CREATE TABLE IF NOT EXISTS snapshots(
              provider TEXT PRIMARY KEY, content_hash TEXT NOT NULL,
              payload TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS change_jobs(
              id INTEGER PRIMARY KEY, provider TEXT NOT NULL,
              content_hash TEXT NOT NULL, task TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT, created_at TEXT NOT NULL,
              UNIQUE(provider,content_hash,task));
            """)

    def _connect(self):
        db=sqlite3.connect(self.path,timeout=30,isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def reserve(self,provider: str,limit: int=2,now: datetime|None=None) -> int|None:
        if limit<0: raise ValueError("limit must be >= 0")
        now=now or datetime.now(timezone.utc)
        day=now.astimezone(TZ).date().isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used=db.execute("SELECT COUNT(*) FROM fetch_attempts WHERE provider=? AND day=?",
                            (provider,day)).fetchone()[0]
            if used>=limit:
                db.rollback()
                return None
            cur=db.execute("INSERT INTO fetch_attempts(provider,day,started_at,status) VALUES(?,?,?,?)",
                           (provider,day,now.isoformat(),"reserved"))
            db.commit()
            return cur.lastrowid

    def complete(self,attempt_id:int, status:str,error:str=""):
        with self._connect() as db:
            db.execute("UPDATE fetch_attempts SET status=?,error=? WHERE id=?",
                       (status,error,attempt_id))

    def latest(self,provider:str):
        with self._connect() as db:
            row=db.execute("SELECT content_hash,payload,updated_at FROM snapshots WHERE provider=?",
                           (provider,)).fetchone()
            return None if row is None else {"hash":row[0],"payload":json.loads(row[1]),"updated_at":row[2]}

    def commit_snapshot(self,provider:str,payload,now:datetime|None=None):
        now=now or datetime.now(timezone.utc)
        encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
        fingerprint=canonical_hash(payload)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous=db.execute("SELECT content_hash FROM snapshots WHERE provider=?",
                                (provider,)).fetchone()
            changed=previous is None or previous[0]!=fingerprint
            if changed:
                db.execute("""INSERT INTO snapshots(provider,content_hash,payload,updated_at)
                  VALUES(?,?,?,?) ON CONFLICT(provider) DO UPDATE SET
                  content_hash=excluded.content_hash,payload=excluded.payload,updated_at=excluded.updated_at""",
                  (provider,fingerprint,encoded,now.isoformat()))
                for task in CHANGE_PIPELINE:
                    db.execute("""INSERT OR IGNORE INTO change_jobs(provider,content_hash,task,created_at)
                      VALUES(?,?,?,?)""",(provider,fingerprint,task,now.isoformat()))
            db.commit()
        return changed,fingerprint

    def pending_jobs(self,limit:int=100):
        with self._connect() as db:
            rows=db.execute("""SELECT id,provider,content_hash,task,attempts FROM change_jobs
                 WHERE status='pending' ORDER BY id LIMIT ?""",(limit,)).fetchall()
            return [dict(zip(("id","provider","content_hash","task","attempts"),r)) for r in rows]

    def finish_job(self,job_id:int,error:str|None=None):
        with self._connect() as db:
            if error:
                db.execute("""UPDATE change_jobs SET attempts=attempts+1,last_error=?,
                    status=CASE WHEN attempts+1>=3 THEN 'failed' ELSE 'pending' END WHERE id=?""",
                    (error,job_id))
            else:
                db.execute("UPDATE change_jobs SET status='done',attempts=attempts+1 WHERE id=?",(job_id,))

    def provider_status(self):
        with self._connect() as db:
            return [dict(provider=r[0],last_refresh=r[1],pending=r[2]) for r in
                db.execute("""SELECT s.provider,s.updated_at,
                 (SELECT COUNT(*) FROM change_jobs j WHERE j.provider=s.provider AND j.status='pending')
                 FROM snapshots s ORDER BY s.provider""").fetchall()]
