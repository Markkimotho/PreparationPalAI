import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from billing import db, ledger, revenuecat
from billing.api import app
from billing.packs import STORE_PACKS

AUTH_VALUE = 'Bearer rc-webhook-secret'
SIGNING = 'rc-signing-secret'
PRODUCTS = {'credits_5000': 'store-5', 'credits_10000': 'store-10', 'credits_20000': 'store-20', 'credits_50000': 'store-50'}
client = TestClient(app)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('BILLING_SERVICE_TOKEN', 'svc')
    monkeypatch.setenv('REVENUECAT_WEBHOOK_AUTH', AUTH_VALUE)
    monkeypatch.setenv('REVENUECAT_SIGNING_SECRET', SIGNING)
    monkeypatch.setenv('REVENUECAT_PRODUCTS', json.dumps(PRODUCTS))
    monkeypatch.setenv('REVENUECAT_SANDBOX_ACCOUNTS', 'u-reviewer')
    monkeypatch.delenv('REVENUECAT_ACCEPT_SANDBOX', raising=False)


def event(kind='NON_RENEWING_PURCHASE', event_id='evt_1', txn='2000000123', product='credits_10000', user='u-alice',
          environment='PRODUCTION', price=9.99, **extra):
    return {'api_version': '1.0', 'event': {'id': event_id, 'type': kind, 'app_user_id': user, 'original_app_user_id': user,
            'aliases': [user], 'product_id': product, 'transaction_id': txn, 'original_transaction_id': txn, 'price': price,
            'currency': 'USD', 'store': 'APP_STORE', 'environment': environment, 'event_timestamp_ms': 1_794_900_000_000} | extra}


def deliver(payload, auth=AUTH_VALUE, secret=SIGNING, ts=None, sign=True):
    body = json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json'}
    if auth is not None:
        headers['Authorization'] = auth
    if sign:
        ts = int(time.time()) if ts is None else ts
        digest = hmac.new(secret.encode(), f'{ts}.'.encode() + body, hashlib.sha256).hexdigest()
        headers['X-RevenueCat-Webhook-Signature'] = f't={ts},v1={digest}'
    return client.post('/webhooks/revenuecat', content=body, headers=headers)


def available(account='u-alice'):
    with db.transaction() as conn:
        return ledger.balance(conn, account).available_micros


def test_store_packs_match_the_published_prices():
    assert [(p.id, p.usd_cents, p.credits_micros) for p in STORE_PACKS.values()] == [
        ('store-5', 499, 5_000_000), ('store-10', 999, 10_000_000), ('store-20', 1999, 20_000_000), ('store-50', 4999, 50_000_000)]


@pytest.mark.parametrize('kwargs', [
    dict(auth=None), dict(auth='Bearer wrong'), dict(secret='wrong-signing'), dict(ts=int(time.time()) - 3600), dict(sign=False),
])
def test_unauthenticated_notifications_credit_nothing(kwargs):
    r = deliver(event(), **kwargs)
    assert r.status_code == 401 and available() == 0


def test_signing_is_optional_when_no_signing_secret_is_configured(monkeypatch):
    monkeypatch.setenv('REVENUECAT_SIGNING_SECRET', '')
    assert deliver(event(), sign=False).json()['outcome'] == 'credited'


def test_notifications_fail_closed_without_an_authorization_value(monkeypatch):
    monkeypatch.setenv('REVENUECAT_WEBHOOK_AUTH', '')
    assert deliver(event()).status_code == 503 and available() == 0


def test_a_purchase_credits_the_pack_once_however_often_it_is_notified():
    outcomes = [deliver(event()).json()['outcome'] for _ in range(5)]
    assert outcomes == ['credited'] + ['duplicate'] * 4 and available() == 10_000_000


def test_credits_come_from_the_pack_not_the_price():
    deliver(event(product='credits_5000', price=0.01))
    assert available() == 5_000_000


@pytest.mark.parametrize('payload,reason', [
    (event(product='credits_unknown'), 'unknown_product'),
    (event(user='$RCAnonymousID:abc123'), 'no_account'),
    (event(kind='INITIAL_PURCHASE'), 'event_type'),
])
def test_unusable_notifications_are_acknowledged_without_credit(payload, reason):
    r = deliver(payload)
    assert r.status_code == 200 and r.json()['outcome'] == f'ignored:{reason}'
    assert available() == 0


def test_an_anonymous_purchase_later_aliased_to_an_account_credits_that_account():
    payload = event(user='$RCAnonymousID:abc')
    payload['event']['aliases'] = ['$RCAnonymousID:abc', 'u-alice']
    assert deliver(payload).json()['outcome'] == 'credited' and available() == 10_000_000


def test_sandbox_purchases_only_credit_the_review_account(monkeypatch):
    assert deliver(event(environment='SANDBOX')).json()['outcome'] == 'ignored:sandbox'
    assert available() == 0
    assert deliver(event(environment='SANDBOX', user='u-reviewer', txn='sbx-1')).json()['outcome'] == 'credited'
    monkeypatch.setenv('REVENUECAT_ACCEPT_SANDBOX', 'true')                      # staging accepts every sandbox purchase
    assert deliver(event(environment='SANDBOX', txn='sbx-2', event_id='evt_2')).json()['outcome'] == 'credited'


def test_a_refund_after_spending_clamps_at_zero_and_applies_once():
    deliver(event())
    with db.transaction() as conn:
        ledger.reserve(conn, 'u-alice', 'r1', 7_000_000, 'chat', 'open-default')
        ledger.settle(conn, 'r1', 7_000_000, 1)
    refund = event(kind='CANCELLATION', event_id='evt_refund', price=-9.99, cancel_reason='CUSTOMER_SUPPORT')
    assert [deliver(refund).json()['outcome'] for _ in range(3)] == ['refunded', 'duplicate', 'duplicate']
    assert available() == 0
    with db.transaction() as conn:
        assert ledger.invariant_holds(conn, 'u-alice')


def test_a_refund_for_an_unknown_purchase_is_ignored():
    assert deliver(event(kind='CANCELLATION', txn='never')).json()['outcome'] == 'ignored:unknown_transaction'


def test_store_packs_are_listed_with_product_ids_for_the_app():
    body = client.get('/v1/packs', params={'channel': 'store'}, headers={'Authorization': 'Bearer svc'}).json()
    assert body['packs'][0] == {'id': 'store-5', 'usd_cents': 499, 'credits': 5000, 'available': True, 'product_id': 'credits_5000'}
    assert [p['id'] for p in client.get('/v1/packs', headers={'Authorization': 'Bearer svc'}).json()['packs']][0] == 'web-5'


def test_signature_parsing_rejects_malformed_headers():
    body = b'{}'
    for header in ('', 't=abc,v1=00', 'v1=' + '0' * 64, 't=1'):
        assert not revenuecat.signature_ok(header, body, SIGNING, now=time.time(), tolerance=300)
