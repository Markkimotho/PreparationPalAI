"""Apply app/migrations/*.sql in order, once each, under an advisory lock."""
import sys
from pathlib import Path

from app import db

MIGRATIONS = Path(__file__).parent / 'migrations'
LOCK_KEY = 7_201_118


def apply() -> list[str]:
    applied: list[str] = []
    with db.transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
        conn.execute('CREATE SCHEMA IF NOT EXISTS app')
        conn.execute('CREATE TABLE IF NOT EXISTS app.schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        done = {r['version'] for r in conn.execute('SELECT version FROM app.schema_migrations')}
        for path in sorted(MIGRATIONS.glob('*.sql')):
            if path.stem not in done:
                conn.execute(path.read_text())
                conn.execute('INSERT INTO app.schema_migrations (version) VALUES (%s)', (path.stem,))
                applied.append(path.stem)
    return applied


if __name__ == '__main__':
    from app.config import get_base_settings
    if not get_base_settings().database_url.get_secret_value():
        sys.exit('Set DATABASE_URL')
    print('applied:', apply() or 'nothing to do')
    db.close()
