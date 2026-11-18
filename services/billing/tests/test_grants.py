from datetime import date, datetime, timezone

import pytest

from billing import ledger
from billing.grants import STARTER_MICROS, GrantResult, expire_starter, grant_starter
from billing.ledger import InsufficientCredits
from billing.pricing import seed_if_empty

DAY = date(2026, 11, 17)


def at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)


def test_grant_once_per_account(conn):
    assert grant_starter(conn, 'a1', DAY) == GrantResult(True, 'granted')
    assert grant_starter(conn, 'a1', DAY) == GrantResult(False, 'already_granted')
    assert grant_starter(conn, 'a1', date(2026, 12, 1)) == GrantResult(False, 'already_granted')
    b = ledger.balance(conn, 'a1')
    assert (b.available_micros, b.starter_micros) == (STARTER_MICROS, STARTER_MICROS) == (500_000, 500_000)
    assert ledger.invariant_holds(conn, 'a1')


def test_daily_cap_blocks_extra_accounts_without_giving_them_anything(conn):
    assert grant_starter(conn, 'a1', DAY, cap=2).granted and grant_starter(conn, 'a2', DAY, cap=2).granted
    assert grant_starter(conn, 'a3', DAY, cap=2) == GrantResult(False, 'daily_cap')
    assert ledger.balance(conn, 'a3') == ledger.Balance(0, 0, 0)
    assert grant_starter(conn, 'a3', date(2026, 11, 18), cap=2).granted   # the cap resets each day


def test_an_already_granted_account_does_not_consume_the_cap(conn):
    grant_starter(conn, 'a1', DAY, cap=1)
    grant_starter(conn, 'a1', DAY, cap=1)
    assert conn.execute('SELECT count FROM billing.grant_days').fetchone()['count'] == 1


def test_open_models_spend_starter_credits_first(conn):
    grant_starter(conn, 'a1', DAY)
    ledger.credit(conn, 'a1', 100_000, 'topup', 'buy-1')
    ledger.reserve(conn, 'a1', 'r1', 200_000, 'quiz_generate', 'open-default')
    ledger.settle(conn, 'r1', 150_000, 1)
    b = ledger.balance(conn, 'a1')
    assert (b.available_micros, b.starter_micros) == (450_000, 350_000)        # purchased 100,000 untouched
    assert ledger.invariant_holds(conn, 'a1')


def test_premium_cannot_use_starter_credits(conn):
    seed_if_empty(conn)
    grant_starter(conn, 'a1', DAY)
    with pytest.raises(InsufficientCredits) as caught:
        ledger.reserve(conn, 'a1', 'r1', 2_000, 'chat', 'premium-claude')
    assert caught.value.premium_requires_purchase is True and caught.value.balance_micros == 500_000
    ledger.credit(conn, 'a1', 1_000, 'topup', 'buy-1')
    with pytest.raises(InsufficientCredits):
        ledger.reserve(conn, 'a1', 'r2', 2_000, 'chat', 'premium-claude')      # only 1,000 purchased
    ledger.reserve(conn, 'a1', 'r3', 1_000, 'chat', 'premium-claude')
    assert ledger.balance(conn, 'a1').starter_micros == 500_000                 # starter untouched by the hold


def test_premium_overrun_beyond_its_hold_is_taken_from_purchased_credits_only(conn):
    seed_if_empty(conn)
    grant_starter(conn, 'a1', DAY)
    ledger.credit(conn, 'a1', 5_000, 'topup', 'buy-1')
    ledger.reserve(conn, 'a1', 'r1', 1_000, 'agent', 'premium-claude')
    result = ledger.settle(conn, 'r1', 9_000, 1)                              # 8,000 over, only 4,000 purchased left
    assert (result.charged_micros, result.written_off_micros) == (5_000, 4_000)
    b = ledger.balance(conn, 'a1')
    assert (b.available_micros, b.starter_micros) == (500_000, 500_000) and ledger.invariant_holds(conn, 'a1')


def test_expiry_removes_only_the_unspent_starter_credits(conn):
    grant_starter(conn, 'a1', DAY)
    ledger.reserve(conn, 'a1', 'r1', 100_000, 'chat', 'open-default')
    ledger.settle(conn, 'r1', 100_000, 1)
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 'buy-1')
    assert expire_starter(conn, at(date(2026, 12, 10))) == 0                  # day 23: still valid
    assert expire_starter(conn, at(date(2026, 12, 18))) == 1                  # day 31: expired
    b = ledger.balance(conn, 'a1')
    assert (b.available_micros, b.starter_micros) == (1_000_000, 0) and ledger.invariant_holds(conn, 'a1')
    assert expire_starter(conn, at(date(2026, 12, 20))) == 0                  # idempotent


def test_expiry_waits_while_a_hold_is_open(conn):
    grant_starter(conn, 'a1', DAY)
    ledger.reserve(conn, 'a1', 'r1', 50_000, 'chat', 'open-default')
    assert expire_starter(conn, at(date(2026, 12, 18))) == 0
    ledger.release(conn, 'r1')
    assert expire_starter(conn, at(date(2026, 12, 18))) == 1
    assert ledger.balance(conn, 'a1') == ledger.Balance(0, 0, 0)
