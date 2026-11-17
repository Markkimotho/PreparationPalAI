import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from billing import db, ledger, paddle
from billing.api import app
from billing.packs import PACKS

SECRET = 'pdl_ntfset_test_secret'
PRICES = {'web-5': 'pri_5', 'web-10': 'pri_10', 'web-20': 'pri_20', 'web-50': 'pri_50'}
AUTH = {'Authorization': 'Bearer svc'}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('BILLING_SERVICE_TOKEN', 'svc')
    monkeypatch.setenv('PADDLE_WEBHOOK_SECRET', SECRET)
    monkeypatch.setenv('PADDLE_PRICE_IDS', json.dumps(PRICES))
    monkeypatch.setenv('PADDLE_API_KEY', 'pdl_sdbx_apikey')
    monkeypatch.setenv('PADDLE_CLIENT_TOKEN', 'test_client_token')
    monkeypatch.setenv('PADDLE_ENVIRONMENT', 'sandbox')


client = TestClient(app)


def sign(body: bytes, secret=SECRET, ts=None, extra_h1=()):
    ts = int(time.time()) if ts is None else ts
    digest = hmac.new(secret.encode(), f'{ts}:'.encode() + body, hashlib.sha256).hexdigest()
    return ';'.join([f'ts={ts}', *[f'h1={h}' for h in extra_h1], f'h1={digest}'])


def deliver(event: dict, **sign_kwargs):
    body = json.dumps(event).encode()
    return client.post('/webhooks/paddle', content=body, headers={'Paddle-Signature': sign(body, **sign_kwargs), 'Content-Type': 'application/json'})


def completed(txn='txn_1', price='pri_10', account='a1', total='1000', currency='USD', **custom):
    return {'event_id': f'evt_{txn}', 'event_type': 'transaction.completed', 'data': {
        'id': txn, 'status': 'completed', 'currency_code': currency, 'custom_data': ({'account_id': account} if account else {}) | custom,
        'items': [{'price': {'id': price}, 'quantity': 1}], 'details': {'totals': {'grand_total': total}}}}


def adjustment(adj, txn='txn_1', total='500', action='refund', status='approved', event='adjustment.created'):
    return {'event_id': f'evt_{adj}_{status}', 'event_type': event, 'data': {
        'id': adj, 'action': action, 'status': status, 'transaction_id': txn, 'totals': {'total': total, 'currency_code': 'USD'}}}


def available(account='a1'):
    with db.transaction() as conn:
        return ledger.balance(conn, account).available_micros


# ---- packs ----------------------------------------------------------------------------------

def test_packs_match_the_published_prices():
    assert [(p.id, p.usd_cents, p.credits_micros) for p in PACKS.values()] == [
        ('web-5', 500, 5_000_000), ('web-10', 1000, 10_500_000), ('web-20', 2000, 21_500_000), ('web-50', 5000, 55_000_000)]


def test_packs_endpoint_lists_packs_with_availability():
    body = client.get('/v1/packs', headers=AUTH).json()
    assert [p['id'] for p in body['packs']] == ['web-5', 'web-10', 'web-20', 'web-50'] and all(p['available'] for p in body['packs'])


# ---- signatures ------------------------------------------------------------------------------

def test_a_valid_signature_is_accepted():
    body = b'{"a":1}'
    assert paddle.verify(sign(body), body, SECRET, now=time.time(), tolerance=300)


@pytest.mark.parametrize('header_for,body', [
    (lambda b: sign(b, secret='wrong'), b'{"a":1}'),
    (lambda b: sign(b'{"a":2}'), b'{"a":1}'),                                  # body changed after signing
    (lambda b: sign(b, ts=int(time.time()) - 3600), b'{"a":1}'),               # replayed an hour later
    (lambda b: sign(b, ts=int(time.time()) + 3600), b'{"a":1}'),               # from the future
    (lambda b: '', b'{"a":1}'),
    (lambda b: 'ts=abc;h1=zz', b'{"a":1}'),
    (lambda b: 'h1=' + 'a' * 64, b'{"a":1}'),                                    # no timestamp
])
def test_bad_signatures_are_rejected(header_for, body):
    assert not paddle.verify(header_for(body), body, SECRET, now=time.time(), tolerance=300)


def test_any_matching_signature_is_accepted_during_secret_rotation():
    body = b'{"a":1}'
    assert paddle.verify(sign(body, extra_h1=['0' * 64]), body, SECRET, now=time.time(), tolerance=300)


def test_a_webhook_with_a_bad_signature_credits_nothing():
    body = json.dumps(completed()).encode()
    r = client.post('/webhooks/paddle', content=body, headers={'Paddle-Signature': sign(body, secret='wrong')})
    assert r.status_code == 401 and available() == 0


def test_webhooks_fail_closed_when_no_secret_is_configured(monkeypatch):
    monkeypatch.setenv('PADDLE_WEBHOOK_SECRET', '')
    assert deliver(completed()).status_code == 503 and available() == 0


# ---- purchases -------------------------------------------------------------------------------

def test_a_completed_purchase_credits_the_pack_once_however_often_paddle_retries():
    outcomes = [deliver(completed()).json()['outcome'] for _ in range(5)]
    assert outcomes == ['credited'] + ['duplicate'] * 4
    assert available() == 10_500_000


def test_credits_come_from_the_pack_table_not_the_amount_paid():
    deliver(completed(price='pri_5', total='1'))                                # local currency or a discount cannot change credits
    assert available() == 5_000_000


@pytest.mark.parametrize('event,reason', [
    (completed(price='pri_unknown'), 'unknown_price'),
    (completed(account=None), 'no_account'),
])
def test_unusable_purchases_are_acknowledged_but_not_credited(event, reason):
    r = deliver(event)
    assert r.status_code == 200 and r.json()['outcome'] == f'ignored:{reason}' and available() == 0


def test_other_events_are_acknowledged_and_ignored():
    r = deliver({'event_id': 'e', 'event_type': 'customer.created', 'data': {'id': 'ctm_1'}})
    assert r.status_code == 200 and r.json()['outcome'] == 'ignored:event_type'


# ---- refunds and chargebacks -----------------------------------------------------------------

def test_partial_refunds_and_a_chargeback_apply_once_each_and_never_below_zero():
    deliver(completed())                                                       # web-10: 10,500,000 for 1000 cents
    assert deliver(adjustment('adj_1', total='500')).json()['outcome'] == 'refunded'
    assert available() == 10_500_000 - 5_250_000
    assert deliver(adjustment('adj_1', total='500')).json()['outcome'] == 'duplicate'
    deliver(adjustment('adj_2', total='250'))
    assert available() == 10_500_000 - 5_250_000 - 2_625_000
    with db.transaction() as conn:                                             # the learner spends most of what is left
        ledger.reserve(conn, 'a1', 'r1', 2_000_000, 'chat', 'open-default')
        ledger.settle(conn, 'r1', 2_000_000, 1)
    r = deliver(adjustment('adj_3', total='1000', action='chargeback'))
    assert r.json()['outcome'] == 'refunded' and available() == 0
    with db.transaction() as conn:
        assert ledger.invariant_holds(conn, 'a1')


def test_a_refund_waits_for_approval():
    deliver(completed())
    assert deliver(adjustment('adj_1', status='pending_approval')).json()['outcome'] == 'ignored:not_approved'
    assert available() == 10_500_000
    assert deliver(adjustment('adj_1', status='approved', event='adjustment.updated')).json()['outcome'] == 'refunded'
    assert available() == 10_500_000 - 5_250_000


def test_credits_given_back_to_us_are_not_refunds():
    deliver(completed())
    assert deliver(adjustment('adj_9', action='credit')).json()['outcome'] == 'ignored:action'
    assert available() == 10_500_000


def test_an_adjustment_for_an_unknown_purchase_is_ignored():
    assert deliver(adjustment('adj_1', txn='txn_never')).json()['outcome'] == 'ignored:unknown_transaction'


# ---- checkout --------------------------------------------------------------------------------

def paddle_api(calls, status=201):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.host, request.url.path, request.headers['authorization'], json.loads(request.content)))
        return httpx.Response(status, json={'data': {'id': 'txn_new'}} if status == 201 else {'error': {'code': 'bad'}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_checkout_creates_a_paddle_transaction_tagged_with_the_account(monkeypatch):
    calls = []
    monkeypatch.setattr(paddle, 'http_client', lambda: paddle_api(calls))
    r = client.post('/v1/checkout', json={'account_id': 'a1', 'pack': 'web-20'}, headers=AUTH)
    assert r.status_code == 200 and r.json() == {'transaction_id': 'txn_new', 'client_token': 'test_client_token', 'environment': 'sandbox'}
    host, path, auth, body = calls[0]
    assert (host, path, auth) == ('sandbox-api.paddle.com', '/transactions', 'Bearer pdl_sdbx_apikey')
    assert body == {'items': [{'price_id': 'pri_20', 'quantity': 1}], 'custom_data': {'account_id': 'a1', 'pack': 'web-20'}}


def test_checkout_refuses_closed_accounts_unknown_packs_and_missing_configuration(monkeypatch):
    monkeypatch.setattr(paddle, 'http_client', lambda: paddle_api([]))
    with db.transaction() as conn:
        ledger.close_account(conn, 'gone')
    assert client.post('/v1/checkout', json={'account_id': 'gone', 'pack': 'web-5'}, headers=AUTH).status_code == 403
    assert client.post('/v1/checkout', json={'account_id': 'a1', 'pack': 'web-999'}, headers=AUTH).status_code == 422
    monkeypatch.setenv('PADDLE_API_KEY', '')
    assert client.post('/v1/checkout', json={'account_id': 'a1', 'pack': 'web-5'}, headers=AUTH).status_code == 503


def test_a_paddle_failure_during_checkout_is_a_clear_502(monkeypatch):
    monkeypatch.setattr(paddle, 'http_client', lambda: paddle_api([], status=400))
    r = client.post('/v1/checkout', json={'account_id': 'a1', 'pack': 'web-5'}, headers=AUTH)
    assert r.status_code == 502 and 'payment provider' in r.json()['detail']


def test_checkout_needs_the_service_token():
    assert TestClient(app).post('/v1/checkout', json={'account_id': 'a1', 'pack': 'web-5'}).status_code == 401
