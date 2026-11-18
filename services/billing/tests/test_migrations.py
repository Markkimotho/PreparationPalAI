import psycopg
import pytest

from billing import db as database
from billing.migrate import apply_migrations


def test_migrations_apply_twice_idempotently():
    first = apply_migrations()
    second = apply_migrations()
    assert second == [] and isinstance(first, list)
    with database.transaction() as conn:
        versions = [r['version'] for r in conn.execute('SELECT version FROM billing.schema_migrations ORDER BY version')]
    assert versions == sorted(set(versions)) and versions[0] == '001_init'


def seed(conn):
    conn.execute("INSERT INTO billing.accounts (id) VALUES ('a1')")
    conn.execute("INSERT INTO billing.balances (account_id) VALUES ('a1')")
    conn.execute("INSERT INTO billing.ledger (account_id, amount_micros, kind, ref) VALUES ('a1', 5000, 'topup', 'p1')")


def test_ledger_rejects_update_and_delete():
    with database.transaction() as conn:
        seed(conn)
    for statement in ("UPDATE billing.ledger SET amount_micros = 1", "DELETE FROM billing.ledger"):
        with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
            with database.transaction() as conn:
                conn.execute(statement)


def test_ledger_kind_is_restricted():
    with pytest.raises(psycopg.errors.CheckViolation):
        with database.transaction() as conn:
            conn.execute("INSERT INTO billing.accounts (id) VALUES ('a1')")
            conn.execute("INSERT INTO billing.ledger (account_id, amount_micros, kind, ref) VALUES ('a1', 1, 'bonus', 'x')")


def test_ledger_kind_and_ref_are_unique_for_idempotency():
    with database.transaction() as conn:
        seed(conn)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with database.transaction() as conn:
            conn.execute("INSERT INTO billing.ledger (account_id, amount_micros, kind, ref) VALUES ('a1', 5000, 'topup', 'p1')")


@pytest.mark.parametrize('column,value', [('available_micros', -1), ('reserved_micros', -1), ('starter_micros', -1)])
def test_balances_cannot_go_negative(column, value):
    with pytest.raises(psycopg.errors.CheckViolation):
        with database.transaction() as conn:
            conn.execute("INSERT INTO billing.accounts (id) VALUES ('a1')")
            conn.execute(f"INSERT INTO billing.balances (account_id, {column}) VALUES ('a1', {value})")


def test_starter_credit_cannot_exceed_available():
    with pytest.raises(psycopg.errors.CheckViolation):
        with database.transaction() as conn:
            conn.execute("INSERT INTO billing.accounts (id) VALUES ('a1')")
            conn.execute("INSERT INTO billing.balances (account_id, available_micros, starter_micros) VALUES ('a1', 100, 200)")


def test_payment_provider_reference_is_unique():
    sql = ("INSERT INTO billing.payments (provider, provider_ref, account_id, gross_minor, currency, credits_micros, status) "
           "VALUES ('paddle', 'txn_1', 'a1', 500, 'USD', 5000000, 'completed')")
    with database.transaction() as conn:
        conn.execute("INSERT INTO billing.accounts (id) VALUES ('a1')")
        conn.execute(sql)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with database.transaction() as conn:
            conn.execute(sql)


def test_reservation_status_is_restricted():
    with pytest.raises(psycopg.errors.CheckViolation):
        with database.transaction() as conn:
            conn.execute("INSERT INTO billing.accounts (id) VALUES ('a1')")
            conn.execute("INSERT INTO billing.reservations (request_id, account_id, amount_micros, action, alias, status) "
                         "VALUES ('r', 'a1', 10, 'chat', 'open-default', 'weird')")


def test_bootstrap_applies_migrations_and_seeds_prices_exactly_once():
    """A fresh deployment must be able to price actions without anyone running extra commands."""
    from billing.migrate import bootstrap
    from billing.pricing import current_prices
    first = bootstrap()
    assert first['prices_seeded'] is False or first['prices_seeded'] is True   # tests clean tables, so seeding state varies
    with database.transaction() as conn:
        assert {'open-default', 'guard', 'embed-default', 'premium-claude'} <= set(current_prices(conn))
    assert bootstrap()['prices_seeded'] is False          # second boot must not publish a new version
    with database.transaction() as conn:
        assert {p.version for p in current_prices(conn).values()} == {1}
