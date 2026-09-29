#!/usr/bin/env python3
"""Cron/systemd entrypoint for provider refresh.

Actual provider registry is intentionally injected by modules.provider_registry.
Missing registry means a safe no-op, not accidental live scraping.
"""
from datetime import datetime
import json

from modules.refresh_orchestrator import run_refresh_batch

try:
    from modules.provider_registry import build_refresh_jobs
except ImportError:
    def build_refresh_jobs():
        return []

results=run_refresh_batch(build_refresh_jobs())
print(json.dumps([r.__dict__ for r in results], ensure_ascii=False, default=str))
