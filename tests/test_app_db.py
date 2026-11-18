import psycopg
import pytest
from pydantic import ValidationError

from app import db, migrate_db
from app.config import Settings
from tests.support.pg import URL

pytestmark = pytest.mark.usefixtures('pg_session')

USER_TABLES = ['flashcard_decks', 'coach_sessions', 'drawings', 'ingestion_jobs', 'usage_events', 'chunks', 'learner_profiles']


def test_migrations_apply_twice_idempotently():
    assert migrate_db.apply() == []
    with db.transaction() as conn:
        versions = [r['version'] for r in conn.execute('SELECT version FROM app.schema_migrations ORDER BY version')]
    assert versions and versions == sorted(set(versions))


@pytest.mark.parametrize('table', USER_TABLES)
def test_every_user_table_is_scoped_by_workspace(table):
    with db.transaction() as conn:
        column = conn.execute("SELECT is_nullable FROM information_schema.columns WHERE table_schema='app' AND table_name=%s AND column_name='workspace'",
                              (table,)).fetchone()
        assert column and column['is_nullable'] == 'NO', f'{table} needs a NOT NULL workspace column'
        leading = conn.execute(
            "SELECT count(*) AS n FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
            "JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=i.indkey[0] WHERE n.nspname='app' AND t.relname=%s AND a.attname='workspace'",
            (table,)).fetchone()['n']
        assert leading >= 1, f'{table} needs an index that starts with workspace'


def test_a_new_user_table_cannot_ship_unscoped():
    """Any table in the app schema other than the allow-listed system tables must be a scoped user table."""
    with db.transaction() as conn:
        names = {r['table_name'] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='app'")}
    assert names - {'schema_migrations', 'workers'} == set(USER_TABLES)


def test_a_failed_transaction_leaves_nothing_behind(pg):
    with pytest.raises(RuntimeError):
        with pg.transaction() as conn:
            conn.execute("INSERT INTO app.usage_events (workspace, identity, at) VALUES ('w', 'i', 1)")
            raise RuntimeError('boom')
    with pg.transaction() as conn:
        assert conn.execute('SELECT count(*) AS n FROM app.usage_events').fetchone()['n'] == 0


def test_the_pool_recovers_after_a_connection_is_killed(pg):
    with pg.transaction() as conn:
        conn.execute('SELECT 1')
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'app' AND pid <> pg_backend_pid() "
                      "AND application_name = 'preparationpal-app'")
    with pg.transaction() as conn:
        assert conn.execute('SELECT 1 AS ok').fetchone()['ok'] == 1


def test_files_remain_the_default_storage_backend():
    assert Settings(_env_file=None).storage_backend == 'files'
    assert db.enabled() is False


def test_postgres_storage_needs_a_database_url():
    with pytest.raises(ValidationError, match='DATABASE_URL'):
        Settings(_env_file=None, storage_backend='postgres')
    s = Settings(_env_file=None, storage_backend='postgres', database_url='postgresql://u:p@db:5432/app')
    assert 'p@db' not in repr(s)             # the password never appears in logs or reprs
