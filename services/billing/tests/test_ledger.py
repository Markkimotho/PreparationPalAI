import random

import pytest

from billing import db, ledger
from billing.ledger import InsufficientCredits
from tests.helpers import fund, state


def total(conn, account='a1'):
    return conn.execute('SELECT COALESCE(SUM(amount_micros), 0) AS t FROM billing.ledger WHERE account_id = %s', (account,)).fetchone()['t']


def test_reserve_settle_math(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    assert state(conn) == (7_000, 3_000)
    result = ledger.settle(conn, 'r1', 1_200, price_version=1)
    assert (result.charged_micros, result.written_off_micros, result.balance_micros) == (1_200, 0, 8_800)
    assert state(conn) == (8_800, 0)
    assert total(conn) == 8_800 and ledger.invariant_holds(conn, 'a1')


def test_settle_above_reservation_charges_actual(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 1_000, 'agent', 'open-default')
    result = ledger.settle(conn, 'r1', 1_500, 1)
    assert (result.charged_micros, result.written_off_micros) == (1_500, 0)
    assert state(conn) == (8_500, 0) and ledger.invariant_holds(conn, 'a1')


def test_settle_beyond_balance_writes_off_and_never_goes_negative(conn):
    fund(conn, micros=1_000)
    ledger.reserve(conn, 'a1', 'r1', 1_000, 'agent', 'open-default')
    result = ledger.settle(conn, 'r1', 1_500, 1)
    assert (result.charged_micros, result.written_off_micros, result.balance_micros) == (1_000, 500, 0)
    assert state(conn) == (0, 0) and ledger.invariant_holds(conn, 'a1')


def test_reserve_refused_when_funds_are_short(conn):
    fund(conn, micros=500)
    with pytest.raises(InsufficientCredits) as caught:
        ledger.reserve(conn, 'a1', 'r1', 600, 'chat', 'open-default')
    assert (caught.value.balance_micros, caught.value.required_micros) == (500, 600)


def test_reserving_for_an_unknown_account_is_insufficient_not_a_crash(conn):
    with pytest.raises(InsufficientCredits) as caught:
        ledger.reserve(conn, 'nobody', 'r1', 1, 'chat', 'open-default')
    assert caught.value.balance_micros == 0


def test_reserve_same_request_twice_is_a_single_hold(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    assert state(conn) == (7_000, 3_000)


def test_settle_twice_and_release_after_settle_are_noops(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    first = ledger.settle(conn, 'r1', 1_000, 1)
    again = ledger.settle(conn, 'r1', 9_999, 1)
    ledger.release(conn, 'r1')
    assert (first.charged_micros, again.charged_micros) == (1_000, 1_000)
    assert state(conn) == (9_000, 0)


def test_release_returns_the_hold(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 4_000, 'chat', 'open-default')
    ledger.release(conn, 'r1')
    ledger.release(conn, 'r1')
    ledger.release(conn, 'never-existed')
    assert state(conn) == (10_000, 0) and total(conn) == 10_000


def test_late_settle_after_the_sweeper_released_the_hold_still_charges(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    ledger.release(conn, 'r1')          # sweeper gave up on a slow stream
    result = ledger.settle(conn, 'r1', 1_200, 1)
    assert result.charged_micros == 1_200 and state(conn) == (8_800, 0)
    assert ledger.invariant_holds(conn, 'a1')


def test_topup_same_provider_reference_credits_once(conn):
    assert ledger.record_topup(conn, 'paddle', 'txn_1', 'a1', 500, 'USD', 4_250_000) == 4_250_000
    assert ledger.record_topup(conn, 'paddle', 'txn_1', 'a1', 500, 'USD', 4_250_000) == 4_250_000
    assert state(conn) == (4_250_000, 0)
    assert conn.execute('SELECT count(*) AS n FROM billing.payments').fetchone()['n'] == 1


def test_refund_after_spend_clamps_at_zero_and_reports_the_shortfall(conn):
    ledger.record_topup(conn, 'paddle', 'txn_1', 'a1', 500, 'USD', 5_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    ledger.settle(conn, 'r1', 3_000, 1)                 # 2,000 left of a 5,000 purchase
    result = ledger.refund(conn, 'paddle', 'txn_1', 5_000)
    assert (result.charged_micros, result.written_off_micros, result.balance_micros) == (2_000, 3_000, 0)
    assert state(conn) == (0, 0) and ledger.invariant_holds(conn, 'a1')
    again = ledger.refund(conn, 'paddle', 'txn_1', 5_000)   # provider retries the webhook
    assert again.charged_micros == 2_000 and state(conn) == (0, 0)


def test_refund_for_an_unknown_payment_is_rejected(conn):
    with pytest.raises(KeyError):
        ledger.refund(conn, 'paddle', 'missing', 100)


def test_adjust_can_charge_but_never_below_zero(conn):
    fund(conn, micros=300)
    result = ledger.adjust(conn, 'a1', -500, 'reconcile:1')
    assert (result.charged_micros, result.written_off_micros) == (300, 200) and state(conn) == (0, 0)
    assert ledger.adjust(conn, 'a1', -500, 'reconcile:1').charged_micros == 300      # idempotent
    ledger.adjust(conn, 'a1', 700, 'goodwill:1')
    assert state(conn) == (700, 0)


def test_history_is_newest_first_and_pages(conn):
    for i in range(5):
        fund(conn, micros=100 + i, ref=f'f{i}')
    page = ledger.history(conn, 'a1', limit=2)
    assert [r.amount_micros for r in page] == [104, 103]
    older = ledger.history(conn, 'a1', limit=10, before_id=page[-1].id)
    assert [r.amount_micros for r in older] == [102, 101, 100]


def test_balance_of_an_unknown_account_is_zero_and_creates_nothing(conn):
    assert ledger.balance(conn, 'ghost') == ledger.Balance(0, 0, 0)
    assert conn.execute("SELECT count(*) AS n FROM billing.accounts WHERE id = 'ghost'").fetchone()['n'] == 0


def test_invariants_hold_after_random_operations(conn):
    rng = random.Random(20261117)
    accounts, live, spent = ['a', 'b', 'c'], [], 0
    for step in range(300):
        account = rng.choice(accounts)
        op = rng.choice(['topup', 'reserve', 'reserve', 'settle', 'settle', 'release', 'adjust', 'refund'])
        try:
            if op == 'topup':
                ledger.record_topup(conn, 'p', f't{step}', account, 100, 'USD', rng.randint(1, 5_000))
            elif op == 'reserve':
                ledger.reserve(conn, account, f'r{step}', rng.randint(1, 3_000), 'chat', 'open-default')
                live.append(f'r{step}')
            elif op == 'settle' and live:
                ledger.settle(conn, live.pop(rng.randrange(len(live))), rng.randint(0, 4_000), 1)
            elif op == 'release' and live:
                ledger.release(conn, live.pop(rng.randrange(len(live))))
            elif op == 'adjust':
                ledger.adjust(conn, account, rng.randint(-2_000, 2_000), f'adj{step}')
            elif op == 'refund':
                ledger.refund(conn, 'p', f't{rng.randint(0, step)}', rng.randint(1, 2_000))
        except (InsufficientCredits, KeyError):
            pass
        for acct in accounts:
            assert ledger.invariant_holds(conn, acct), (step, op, acct)
    assert any(ledger.balance(conn, a).available_micros > 0 for a in accounts)
    kinds = {r['kind']: r['n'] for r in conn.execute('SELECT kind, count(*) AS n FROM billing.ledger GROUP BY kind')}
    assert {'topup', 'reserve', 'settle', 'release', 'adjust', 'refund'} <= set(kinds), kinds   # the run is not vacuous
    assert conn.execute("SELECT count(*) AS n FROM billing.reservations WHERE status = 'settled' AND charged_micros > 0").fetchone()['n'] > 5


# ---- closing an account -----------------------------------------------------------------

def test_closing_releases_open_holds_and_refuses_new_ones(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    ledger.close_account(conn, 'a1')
    assert state(conn) == (10_000, 0) and ledger.invariant_holds(conn, 'a1')
    with pytest.raises(ledger.AccountClosed):
        ledger.reserve(conn, 'a1', 'r2', 1, 'chat', 'open-default')


def test_closing_twice_and_closing_an_unknown_account_are_harmless(conn):
    fund(conn, micros=500)
    ledger.close_account(conn, 'a1')
    ledger.close_account(conn, 'a1')
    ledger.close_account(conn, 'never-existed')
    assert ledger.balance(conn, 'a1').available_micros == 500          # the ledger is kept, anonymously
    with pytest.raises(ledger.AccountClosed):
        ledger.reserve(conn, 'never-existed', 'r9', 1, 'chat', 'open-default')   # tombstone: cannot be resurrected


def test_a_late_settle_for_a_closed_account_still_charges(conn):
    fund(conn, micros=10_000)
    ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')
    ledger.close_account(conn, 'a1')
    assert ledger.settle(conn, 'r1', 1_000, 1).charged_micros == 1_000 and ledger.invariant_holds(conn, 'a1')


def test_a_closed_account_gets_no_starter_allowance(conn):
    from datetime import date
    from billing.grants import grant_starter
    ledger.close_account(conn, 'a1')
    assert grant_starter(conn, 'a1', date(2026, 11, 17)).reason == 'account_closed'
