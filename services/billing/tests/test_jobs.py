from datetime import datetime, timedelta, timezone

import httpx
import pytest

from billing import jobs, ledger
from billing.pricing import current_prices, seed_if_empty
from billing.jobs import PriceDiff, ReconcileReport

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
KEY = 'preparationpal-prod'


@pytest.fixture
def prices(conn):
    seed_if_empty(conn)
    return current_prices(conn)


def age(conn, request_id, minutes):
    conn.execute("UPDATE billing.reservations SET created_at = %s WHERE request_id = %s", (NOW - timedelta(minutes=minutes), request_id))


def row(reservation, alias, i, o, account='a1', status='success', key=KEY, call_id=None):
    return {'request_id': call_id or f'{reservation}-{alias}-{i}-{o}', 'end_user': account, 'model_group': alias,
            'prompt_tokens': i, 'completion_tokens': o, 'status': status,
            'metadata': {'user_api_key_alias': key, 'spend_logs_metadata': {'request_id': reservation, 'action': 'chat'} if reservation else None}}


def test_sweep_releases_only_stale_holds(conn):
    ledger.credit(conn, 'a1', 10_000, 'topup', 't1')
    ledger.reserve(conn, 'a1', 'old', 3_000, 'chat', 'open-default')
    ledger.reserve(conn, 'a1', 'fresh', 2_000, 'chat', 'open-default')
    age(conn, 'old', 20)
    age(conn, 'fresh', 5)
    assert jobs.sweep(conn, NOW) == 1
    assert ledger.balance(conn, 'a1') == ledger.Balance(8_000, 2_000, 0)
    assert jobs.sweep(conn, NOW) == 0
    assert ledger.invariant_holds(conn, 'a1')


def test_reconcile_finds_nothing_when_every_call_was_settled(conn, prices):
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 't1')
    ledger.reserve(conn, 'a1', 'r1', 100_000, 'chat', 'open-default')
    ledger.settle(conn, 'r1', 13_552, prices['guard'].version)
    rows = [row('r1', 'open-default', 8000, 2500), row('r1', 'guard', 12000, 80)]
    assert jobs.reconcile(conn, rows, KEY) == ReconcileReport(matched=1, missing_in_ledger=0, drift_micros=0)
    assert ledger.balance(conn, 'a1').available_micros == 1_000_000 - 13_552


def test_reconcile_charges_usage_that_never_settled_exactly_once(conn, prices):
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 't1')
    ledger.reserve(conn, 'a1', 'r1', 100_000, 'chat', 'open-default')
    age(conn, 'r1', 60)
    jobs.sweep(conn, NOW)                                               # app crashed; the hold was swept
    rows = [row('r1', 'open-default', 8000, 2500), row('r1', 'guard', 12000, 80)]
    first = jobs.reconcile(conn, rows, KEY)
    again = jobs.reconcile(conn, rows, KEY)
    assert first == ReconcileReport(matched=0, missing_in_ledger=1, drift_micros=13_552)
    assert again == ReconcileReport(matched=1, missing_in_ledger=0, drift_micros=0)      # already corrected, nothing new
    assert ledger.balance(conn, 'a1').available_micros == 1_000_000 - 13_552
    assert ledger.invariant_holds(conn, 'a1')


def test_reconcile_charges_a_reservation_billing_never_saw(conn, prices):
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 't1')
    report = jobs.reconcile(conn, [row('ghost', 'guard', 1000, 10, account='a1')], KEY)
    assert report.missing_in_ledger == 1 and ledger.balance(conn, 'a1').available_micros == 1_000_000 - 184   # (1000 x 0.12 + 10 x 0.24) x 1.5 = 183.6 -> 184


def test_reconcile_charges_the_difference_when_settle_undercounted(conn, prices):
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 't1')
    ledger.reserve(conn, 'a1', 'r1', 100_000, 'chat', 'open-default')
    ledger.settle(conn, 'r1', 2_189, prices['guard'].version)           # only the guard line was settled
    rows = [row('r1', 'open-default', 8000, 2500), row('r1', 'guard', 12000, 80)]
    report = jobs.reconcile(conn, rows, KEY)
    assert report == ReconcileReport(matched=0, missing_in_ledger=0, drift_micros=11_363)
    assert ledger.balance(conn, 'a1').available_micros == 1_000_000 - 13_552


def test_reconcile_ignores_other_apps_unscoped_calls_and_failures(conn, prices):
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 't1')
    rows = [row('r9', 'open-default', 5000, 500, key='some-other-app'),
            row(None, 'open-default', 5000, 500),                       # no correlation data at all
            dict(row('r8', 'open-default', 5000, 500), metadata={'user_api_key_alias': KEY, 'spend_logs_metadata': {'request_id': 'r8', 'action': 'unscoped'}}),
            row('r9', 'open-default', 5000, 500, status='failure')]
    assert jobs.reconcile(conn, rows, KEY) == ReconcileReport(0, 0, 0)
    assert ledger.balance(conn, 'a1').available_micros == 1_000_000


def test_reconcile_never_drives_a_balance_negative(conn, prices):
    ledger.credit(conn, 'a1', 100, 'topup', 't1')
    jobs.reconcile(conn, [row('r1', 'open-default', 8000, 2500)], KEY)
    assert ledger.balance(conn, 'a1').available_micros == 0 and ledger.invariant_holds(conn, 'a1')


def info(alias, input_per_m, output_per_m):
    return {'model_name': alias, 'model_info': {'input_cost_per_token': input_per_m / 1e6, 'output_cost_per_token': output_per_m / 1e6}}


def test_check_prices_flags_only_the_changed_alias(conn, prices):
    model_info = [info('open-default', 0.40, 1.75), info('guard', 0.12, 0.24), info('open-fast', 0.20, 0.24),
                  info('open-default-fallback', 9, 9), info('unpriced-model', 1, 1)]
    diffs = jobs.check_prices(conn, model_info)
    assert [(d.alias, d.ours_input, d.gateway_input) for d in diffs] == [('open-fast', 0.12, 0.20)]


def test_check_prices_is_quiet_when_everything_matches(conn, prices):
    assert jobs.check_prices(conn, [info('open-default', 0.40, 1.75)]) == []


def test_spend_rows_are_fetched_page_by_page():
    pages = {1: [{'request_id': 'a'}, {'request_id': 'b'}], 2: [{'request_id': 'c'}], 3: []}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers['authorization'] == 'Bearer admin-key'
        page = int(request.url.params['page'])
        assert request.url.params['start_date'] == '2026-11-16 00:00:00' and request.url.params['end_date'] == '2026-11-17 00:00:00'
        return httpx.Response(200, json={'data': pages[page], 'total': 3})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url='http://gateway')
    rows = jobs.fetch_spend_rows(client, 'admin-key', datetime(2026, 11, 16).date(), page_size=2)
    assert [r['request_id'] for r in rows] == ['a', 'b', 'c']


def test_job_results_are_reported_through_the_metrics_endpoint(conn, monkeypatch):
    from fastapi.testclient import TestClient
    from billing.api import app
    jobs.record_run(conn, 'reconcile', {'drift_micros': 13_552, 'matched': 4, 'missing_in_ledger': 1}, True)
    jobs.record_run(conn, 'check-prices', {'price_diffs': []}, False)
    jobs.record_run(conn, 'reconcile', {'drift_micros': 500, 'matched': 5, 'missing_in_ledger': 0}, True)   # the latest run wins
    conn.commit()
    text = TestClient(app).get('/metrics').text
    assert 'billing_job_problem{job="reconcile"} 1.0' in text and 'billing_job_problem{job="check-prices"} 0.0' in text
    assert 'billing_reconcile_drift_micros 500.0' in text and 'billing_price_drift 0.0' in text
    assert 'billing_job_last_run_timestamp{job="reconcile"}' in text


def test_reports_are_plain_integers_that_serialize_even_after_a_correction(conn, prices):
    """Postgres returns SUM(bigint) as Decimal; a report built from it must still be JSON-safe."""
    import json
    from dataclasses import asdict
    ledger.credit(conn, 'a1', 1_000_000, 'topup', 't1')
    ledger.reserve(conn, 'a1', 'r1', 100_000, 'chat', 'open-default')
    age(conn, 'r1', 60)
    jobs.sweep(conn, NOW)
    rows = [row('r1', 'open-default', 8000, 2500)]
    for _ in range(2):                                          # the second run sees an earlier correction
        report = jobs.reconcile(conn, rows, KEY)
        assert all(type(v) is int for v in asdict(report).values())
        json.dumps(asdict(report))
