"""Durable per-identity request budgets, shared across API processes."""
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException
from app.config import get_base_settings
from app.workspace import workspace_id, identity_id


def consume():
    settings = get_base_settings()
    path = Path(settings.usage_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS usage (workspace TEXT, identity TEXT, at REAL)')
            db.execute('CREATE INDEX IF NOT EXISTS usage_lookup ON usage(workspace,identity,at)')
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            db.execute('DELETE FROM usage WHERE at < ?', (now - 86400,))
            counts = db.execute('SELECT COUNT(*), COALESCE(SUM(at > ?),0) FROM usage WHERE workspace=? AND identity=?',
                (now - 60, workspace_id.get(), identity_id.get())).fetchone()
            if counts[0] >= settings.requests_per_day or counts[1] >= settings.requests_per_minute:
                raise HTTPException(429, 'Study request limit reached. Please retry later.', headers={'Retry-After': '60'})
            db.execute('INSERT INTO usage VALUES (?,?,?)', (workspace_id.get(), identity_id.get(), now))
    finally:
        db.close()
