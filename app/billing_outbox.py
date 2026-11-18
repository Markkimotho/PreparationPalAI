"""Durable queue of usage that could not be settled because billing was unreachable.

A model call that already ran must be charged eventually. Entries are retried at the
start of every metered request and by `python -m app.billing_outbox`.
"""
import json
import logging
import sqlite3
import time
from pathlib import Path

from app.billing_client import BillingClient, BillingUnavailable, ReservationMissing
from app.config import get_base_settings

logger = logging.getLogger(__name__)


def _db() -> sqlite3.Connection:
    path = Path(get_base_settings().billing_outbox_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS outbox (request_id TEXT PRIMARY KEY, usage TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL)')
    return db


def enqueue(request_id: str, usage: list[dict]) -> None:
    db = _db()
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO outbox (request_id, usage, created) VALUES (?, ?, ?)', (request_id, json.dumps(usage), time.time()))
    finally:
        db.close()


def pending() -> int:
    db = _db()
    try:
        return db.execute('SELECT count(*) FROM outbox').fetchone()[0]
    finally:
        db.close()


def flush(client: BillingClient, limit: int = 50) -> int:
    """Settle queued usage. Returns how many entries were cleared. Stops at the first outage."""
    db = _db()
    cleared = 0
    try:
        for request_id, usage in db.execute('SELECT request_id, usage FROM outbox ORDER BY created LIMIT ?', (limit,)).fetchall():
            try:
                client.settle(request_id, json.loads(usage))
            except BillingUnavailable:
                db.execute('UPDATE outbox SET attempts = attempts + 1 WHERE request_id = ?', (request_id,))
                db.commit()
                break
            except ReservationMissing:
                logger.error('Dropping outbox usage for a reservation billing does not know', extra={'request_id': request_id})
            with db:
                db.execute('DELETE FROM outbox WHERE request_id = ?', (request_id,))
            cleared += 1
    finally:
        db.close()
    return cleared


if __name__ == '__main__':
    from app.billing_client import get_client
    print('cleared', flush(get_client()), 'still pending', pending())
