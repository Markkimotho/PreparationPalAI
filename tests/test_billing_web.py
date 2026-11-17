import pytest
from fastapi.testclient import TestClient

from app import billing_client, metered
from app.api import app
from app.config import get_base_settings
from tests.support.fake_billing import FakeBilling

client = TestClient(app)


@pytest.fixture
def billing(monkeypatch):
    fake = FakeBilling()
    monkeypatch.setattr(get_base_settings(), 'billing_enabled', True)
    monkeypatch.setattr(metered, 'get_client', lambda: billing_client.BillingClient(client=fake.client()))
    return fake


def test_packs_are_shown_with_prices_and_credits(billing):
    assert client.get('/api/billing/packs').json() == {'packs': [
        {'id': 'web-5', 'price': '$5', 'credits': 5000, 'available': True},
        {'id': 'web-10', 'price': '$10', 'credits': 10500, 'available': False}]}


def test_checkout_is_started_for_the_signed_in_account_only(billing):
    r = client.post('/api/billing/checkout', json={'pack': 'web-5'})
    assert r.status_code == 200 and r.json() == {'transaction_id': 'txn_fake', 'client_token': 'live_client_token', 'environment': 'sandbox'}
    body = next(b for m, p, b in billing.calls if p == '/v1/checkout')
    assert body == {'account_id': 'local', 'pack': 'web-5'}


def test_a_client_cannot_choose_whose_account_is_credited(billing):
    client.post('/api/billing/checkout', json={'pack': 'web-5', 'account_id': 'someone-else'})
    body = next(b for m, p, b in billing.calls if p == '/v1/checkout')
    assert body['account_id'] == 'local'


@pytest.mark.parametrize('status,expected', [(403, 403), (422, 422), (503, 503), (502, 502), (500, 503)])
def test_checkout_failures_are_explained(billing, status, expected):
    billing.checkout_status = status
    r = client.post('/api/billing/checkout', json={'pack': 'web-5'})
    assert r.status_code == expected and r.json()['detail']


def test_history_is_readable_and_hides_internal_holds(billing):
    billing.history_rows = [
        dict(id=6, amount_micros=-1500, hold_micros=-7000, kind='settle', ref='r2', price_version=1, created_at='2026-11-17T10:05:00Z'),
        dict(id=5, amount_micros=0, hold_micros=7000, kind='reserve', ref='r2', price_version=None, created_at='2026-11-17T10:04:00Z'),
        dict(id=4, amount_micros=-300_000, hold_micros=0, kind='adjust', ref='starter-expiry:a', price_version=None, created_at='2026-11-16T00:00:00Z'),
        dict(id=3, amount_micros=5_000_000, hold_micros=0, kind='topup', ref='paddle:txn_1', price_version=None, created_at='2026-11-15T09:00:00Z'),
        dict(id=2, amount_micros=-2_500_000, hold_micros=0, kind='refund', ref='paddle:txn_1:adj_1', price_version=None, created_at='2026-11-15T09:30:00Z'),
        dict(id=1, amount_micros=500_000, hold_micros=0, kind='grant', ref='starter:a', price_version=None, created_at='2026-11-14T08:00:00Z'),
    ]
    entries = client.get('/api/billing/history').json()['entries']
    assert [(e['label'], e['credits']) for e in entries] == [
        ('Study activity', -1.5), ('Free starter credits expired', -300.0), ('Credits purchased', 5000.0),
        ('Refund', -2500.0), ('Free starter credits', 500.0)]
    assert all(set(e) == {'id', 'when', 'label', 'credits'} for e in entries)


def test_history_pages(billing):
    billing.history_rows = [dict(id=i, amount_micros=1000, hold_micros=0, kind='topup', ref=f'p{i}', price_version=None,
                                 created_at='2026-11-17T00:00:00Z') for i in range(10, 0, -1)]
    first = client.get('/api/billing/history', params={'limit': 4}).json()
    assert len(first['entries']) == 4 and first['next_before_id'] == 7
    rest = client.get('/api/billing/history', params={'limit': 10, 'before_id': 7}).json()
    assert [e['id'] for e in rest['entries']] == [6, 5, 4, 3, 2, 1]


def test_billing_pages_are_absent_when_billing_is_off(monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'billing_enabled', False)
    for path in ('/api/billing/packs', '/api/billing/history'):
        assert client.get(path).status_code == 404
    assert client.post('/api/billing/checkout', json={'pack': 'web-5'}).status_code == 404


def test_sign_in_configuration_is_public_but_contains_no_secrets(monkeypatch):
    s = get_base_settings()
    for name, value in dict(auth_mode='oidc', auth_enabled=True, oidc_issuer='https://auth.example.com/oidc',
                            oidc_audience='https://api.example.com', oidc_web_client_id='web-app-id', auth_tokens={}).items():
        monkeypatch.setattr(s, name, value)
    body = client.get('/api/auth/status').json()
    assert {k: body[k] for k in ('enabled', 'mode', 'issuer', 'web')} == {
        'enabled': True, 'mode': 'oidc', 'issuer': 'https://auth.example.com/oidc',
        'web': {'endpoint': 'https://auth.example.com', 'client_id': 'web-app-id', 'resource': 'https://api.example.com'}}


def test_opening_the_balance_offers_the_starter_allowance_first(billing):
    """A new learner must see their free credits on the Account page, not 0 until their first study action."""
    metered._started.clear()
    billing.grant_reason = 'granted'
    client.get('/api/billing/balance')
    paths = [p for _, p, _ in billing.calls]
    assert paths.index('/v1/accounts/local/grants/starter') < paths.index('/v1/accounts/local/balance')


def test_store_packs_carry_the_store_product_id_for_the_phone_app(billing):
    body = client.get('/api/billing/packs', params={'channel': 'store'}).json()
    assert body == {'packs': [{'id': 'store-5', 'price': '$4.99', 'credits': 5000, 'available': True, 'product_id': 'credits_5000'},
                              {'id': 'store-10', 'price': '$9.99', 'credits': 10000, 'available': False, 'product_id': None}]}
    assert client.get('/api/billing/packs', params={'channel': 'gift-cards'}).status_code == 422


def test_the_native_app_learns_its_client_id_from_the_public_status(monkeypatch):
    s = get_base_settings()
    for name, value in dict(auth_mode='oidc', auth_enabled=True, oidc_issuer='https://auth.example.com/oidc', oidc_audience='https://api.example.com',
                            oidc_web_client_id='web-app', oidc_native_client_id='native-app', auth_tokens={}).items():
        monkeypatch.setattr(s, name, value)
    assert client.get('/api/auth/status').json()['native'] == {
        'endpoint': 'https://auth.example.com', 'client_id': 'native-app', 'resource': 'https://api.example.com'}
