"""Durable per-identity request budgets, shared across API processes (SQLite files or Postgres)."""
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException

from app import db
from app.config import get_base_settings
from app.workspace import workspace_id, identity_id

LIMITED = 'Study request limit reached. Please retry later.'


def _check(settings, in_day: int, in_minute: int) -> None:
    if in_day >= settings.requests_per_day or in_minute >= settings.requests_per_minute:
        raise HTTPException(429, LIMITED, headers={'Retry-After': '60'})


def _consume_postgres(settings) -> None:
    workspace, identity, now = workspace_id.get(), identity_id.get(), time.time()
    with db.transaction() as conn:
        # One learner's requests are checked one at a time, so parallel requests cannot all pass.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'usage:{workspace}:{identity}',))
        conn.execute('DELETE FROM app.usage_events WHERE workspace = %s AND identity = %s AND at < %s', (workspace, identity, now - 86400))
        counts = conn.execute('SELECT count(*) AS day, count(*) FILTER (WHERE at > %s) AS minute FROM app.usage_events '
                              'WHERE workspace = %s AND identity = %s', (now - 60, workspace, identity)).fetchone()
        _check(settings, counts['day'], counts['minute'])
        conn.execute('INSERT INTO app.usage_events (workspace, identity, at) VALUES (%s, %s, %s)', (workspace, identity, now))


def _consume_sqlite(settings) -> None:
    path = Path(settings.usage_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        with conn:
            conn.execute('CREATE TABLE IF NOT EXISTS usage (workspace TEXT, identity TEXT, at REAL)')
            conn.execute('CREATE INDEX IF NOT EXISTS usage_lookup ON usage(workspace,identity,at)')
            conn.execute('BEGIN IMMEDIATE')
            now = time.time()
            conn.execute('DELETE FROM usage WHERE at < ?', (now - 86400,))
            counts = conn.execute('SELECT COUNT(*), COALESCE(SUM(at > ?),0) FROM usage WHERE workspace=? AND identity=?',
                                  (now - 60, workspace_id.get(), identity_id.get())).fetchone()
            _check(settings, counts[0], counts[1])
            conn.execute('INSERT INTO usage VALUES (?,?,?)', (workspace_id.get(), identity_id.get(), now))
    finally:
        conn.close()


def consume():
    settings = get_base_settings()
    (_consume_postgres if db.enabled() else _consume_sqlite)(settings)
