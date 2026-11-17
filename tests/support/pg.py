"""Shared fixture for tests that need the throwaway Postgres (tests/support/docker-compose.pg.yml)."""
import os

import pytest

URL = os.environ.get('APP_TEST_DATABASE_URL', 'postgresql://app:test@127.0.0.1:15433/app')
TABLES = 'flashcard_decks, coach_sessions, drawings, ingestion_jobs, workers, usage_events, chunks'


def available() -> bool:
    try:
        import psycopg
        psycopg.connect(URL, connect_timeout=2).close()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope='session')
def pg_session():
    if not available():
        pytest.skip('Postgres test database is not running (docker compose -f tests/support/docker-compose.pg.yml up -d)')
    from app import db, migrate_db
    db.configure(URL, max_size=20)
    migrate_db.apply()
    yield
    db.close()


@pytest.fixture
def pg(pg_session):
    """A clean database for one test."""
    from app import db
    with db.transaction() as conn:
        conn.execute(f'TRUNCATE app.{TABLES.replace(", ", ", app.")} RESTART IDENTITY')
    yield db
