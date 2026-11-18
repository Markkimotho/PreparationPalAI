import os

import pytest

from billing import db as database
from billing.migrate import apply_migrations

TEST_URL = os.environ.get('BILLING_TEST_DATABASE_URL', 'postgresql://billing:test@127.0.0.1:15432/billing')
TABLES = 'ledger, reservations, payments, balances, accounts, prices, grant_days, job_runs, grant_emails'


@pytest.fixture(scope='session', autouse=True)
def configured_database():
    database.configure(TEST_URL, max_size=30)
    apply_migrations()
    yield
    database.close()


@pytest.fixture(autouse=True)
def clean(configured_database):
    with database.transaction() as conn:
        conn.execute(f'TRUNCATE billing.{TABLES.replace(", ", ", billing.")} RESTART IDENTITY CASCADE')
    yield


@pytest.fixture
def conn():
    with database.transaction() as c:
        yield c


@pytest.fixture(autouse=True)
def legacy_grants_without_email(monkeypatch):
    """Most tests are about money, not identity. Email rules have their own file and switch this on."""
    monkeypatch.setenv('BILLING_REQUIRE_VERIFIED_EMAIL', 'false')
