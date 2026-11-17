"""Apply billing/migrations/*.sql in order, once each, under an advisory lock."""
import sys
from pathlib import Path

from billing import db
from billing.settings import get_settings

MIGRATIONS = Path(__file__).parent / 'migrations'
LOCK_KEY = 7_201_117


def apply_migrations() -> list[str]:
    applied: list[str] = []
    with db.transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
        conn.execute('CREATE SCHEMA IF NOT EXISTS billing')
        conn.execute('CREATE TABLE IF NOT EXISTS billing.schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        done = {r['version'] for r in conn.execute('SELECT version FROM billing.schema_migrations')}
        for path in sorted(MIGRATIONS.glob('*.sql')):
            if path.stem not in done:
                conn.execute(path.read_text())
                conn.execute('INSERT INTO billing.schema_migrations (version) VALUES (%s)', (path.stem,))
                applied.append(path.stem)
    return applied


if __name__ == '__main__':
    settings = get_settings()
    if not settings.database_url:
        sys.exit('Set BILLING_DATABASE_URL')
    db.configure(settings.database_url)
    print('applied:', apply_migrations() or 'nothing to do')
    db.close()
