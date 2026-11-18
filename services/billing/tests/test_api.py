import pytest
from fastapi.testclient import TestClient

from billing import db, pricing
from billing.api import app
from billing.pricing import Usage

TOKEN = 'test-service-token'
AUTH = {'Authorization': f'Bearer {TOKEN}'}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('BILLING_SERVICE_TOKEN', TOKEN)
    with db.transaction() as conn:
        pricing.seed_if_empty(conn)
    return TestClient(app, headers=AUTH)


def topup(client, account='a1', micros=1_000_000, ref='t1'):
    return client.post('/v1/payments/topup', json=dict(provider='paddle', provider_ref=ref, account_id=account,
                                                       gross_minor=500, currency='USD', credits_micros=micros))


LINES = [dict(alias='open-default', max_input_tokens=5000, max_output_tokens=2048, calls=2)]


def reserve(client, request_id='r1', alias='open-default', lines=None, account='a1'):
    return client.post('/v1/reservations', json=dict(account_id=account, request_id=request_id, action='chat',
                                                     alias=alias, lines=lines or LINES))


def test_requests_without_the_service_token_are_rejected(client):
    for headers in ({}, {'Authorization': 'Bearer wrong'}, {'Authorization': 'Basic abc'}):
        assert TestClient(app).get('/v1/accounts/a1/balance', headers=headers).status_code == 401
    assert TestClient(app).get('/healthz').status_code == 200


def test_unconfigured_token_fails_closed(client, monkeypatch):
    monkeypatch.setenv('BILLING_SERVICE_TOKEN', '')
    assert client.get('/v1/accounts/a1/balance').status_code == 503


def test_account_balance_and_starter_grant_flow(client):
    assert client.post('/v1/accounts/a1').status_code == 200
    assert client.post('/v1/accounts/a1/grants/starter').json() == {'granted': True, 'reason': 'granted'}
    assert client.post('/v1/accounts/a1/grants/starter').json() == {'granted': False, 'reason': 'already_granted'}
    assert client.get('/v1/accounts/a1/balance').json() == dict(available_micros=500_000, reserved_micros=0, starter_micros=500_000)


def test_unknown_account_balance_is_zero(client):
    assert client.get('/v1/accounts/ghost/balance').json() == dict(available_micros=0, reserved_micros=0, starter_micros=0)


def test_reservation_amount_is_priced_by_billing_not_the_caller(client):
    topup(client)
    prices = _prices()
    expected = 2 * pricing.ceiling_micros(prices['open-default'], 5000, 2048)
    body = reserve(client)
    assert body.status_code == 201 and body.json()['reserved_micros'] == expected
    assert client.get('/v1/accounts/a1/balance').json()['reserved_micros'] == expected


def _prices():
    with db.transaction() as conn:
        return pricing.current_prices(conn)


def test_402_carries_the_numbers_the_app_needs(client):
    topup(client, micros=100)
    response = reserve(client)
    assert response.status_code == 402
    body = response.json()
    assert body['balance_micros'] == 100 and body['required_micros'] > 100 and body['premium_requires_purchase'] is False


def test_premium_with_only_starter_credits_is_402_with_the_flag(client):
    client.post('/v1/accounts/a1/grants/starter')
    response = reserve(client, alias='premium-claude', lines=[dict(alias='premium-claude', max_input_tokens=100, max_output_tokens=100, calls=1)])
    assert response.status_code == 402 and response.json()['premium_requires_purchase'] is True


@pytest.mark.parametrize('bad', [
    dict(alias='qwen2.5:7b'),
    dict(lines=[dict(alias='nope', max_input_tokens=1, max_output_tokens=1, calls=1)]),
    dict(lines=[]),
    dict(lines=[dict(alias='guard', max_input_tokens=-1, max_output_tokens=1, calls=1)]),
    dict(request_id=''),
])
def test_invalid_reservations_are_422(client, bad):
    topup(client)
    payload = dict(account_id='a1', request_id='r1', action='chat', alias='open-default', lines=LINES) | bad
    assert client.post('/v1/reservations', json=payload).status_code == 422


def test_settle_prices_the_usage_server_side(client):
    topup(client)
    reserve(client, lines=[dict(alias='open-default', max_input_tokens=20_000, max_output_tokens=4_000, calls=1),
                           dict(alias='guard', max_input_tokens=20_000, max_output_tokens=500, calls=1)])
    usage = [dict(alias='open-default', input_tokens=8000, output_tokens=2500), dict(alias='guard', input_tokens=12000, output_tokens=80)]
    result = client.post('/v1/reservations/r1/settle', json=dict(usage=usage))
    assert result.status_code == 200
    assert result.json()['charged_micros'] == 13_552 and result.json()['written_off_micros'] == 0
    assert client.get('/v1/accounts/a1/balance').json()['available_micros'] == 1_000_000 - 13_552
    again = client.post('/v1/reservations/r1/settle', json=dict(usage=usage))
    assert again.json()['charged_micros'] == 13_552
    assert client.get('/v1/accounts/a1/balance').json()['available_micros'] == 1_000_000 - 13_552


def test_settle_with_an_unpriced_alias_is_rejected_and_the_hold_stays_open(client):
    topup(client)
    reserve(client)
    response = client.post('/v1/reservations/r1/settle', json=dict(usage=[dict(alias='mystery', input_tokens=1, output_tokens=1)]))
    assert response.status_code == 422
    assert client.get('/v1/accounts/a1/balance').json()['reserved_micros'] > 0


def test_settle_and_release_unknown_reservations(client):
    assert client.post('/v1/reservations/none/settle', json=dict(usage=[])).status_code == 404
    assert client.post('/v1/reservations/none/release').status_code == 204


def test_release_returns_the_hold(client):
    topup(client)
    reserve(client)
    assert client.post('/v1/reservations/r1/release').status_code == 204
    assert client.get('/v1/accounts/a1/balance').json() == dict(available_micros=1_000_000, reserved_micros=0, starter_micros=0)


def test_estimate_matches_the_charge_formula(client):
    response = client.post('/v1/estimate', json=dict(alias='open-default', input_tokens=8000, output_tokens=2500))
    assert response.json() == {'micros': 11_363}
    assert client.post('/v1/estimate', json=dict(alias='nope', input_tokens=1, output_tokens=1)).status_code == 422


def test_prices_are_listed_with_their_version(client):
    body = client.get('/v1/prices').json()
    assert body['version'] == 1 and {p['alias'] for p in body['prices']} >= {'open-default', 'guard', 'premium-claude'}


def test_topup_webhook_is_idempotent_and_refund_clamps(client):
    assert topup(client, micros=5_000).json()['available_micros'] == 5_000
    assert topup(client, micros=5_000).json()['available_micros'] == 5_000
    refund = client.post('/v1/payments/refund', json=dict(provider='paddle', provider_ref='t1', credits_micros=9_000))
    assert refund.json() == dict(clawed_back_micros=5_000, shortfall_micros=4_000, available_micros=0)
    assert client.post('/v1/payments/refund', json=dict(provider='paddle', provider_ref='nope', credits_micros=1)).status_code == 404


def test_history_pages_newest_first(client):
    for i in range(3):
        topup(client, micros=100 + i, ref=f't{i}')
    page = client.get('/v1/accounts/a1/history?limit=2').json()
    assert [r['amount_micros'] for r in page['entries']] == [102, 101] and page['next_before_id']
    older = client.get(f"/v1/accounts/a1/history?limit=2&before_id={page['next_before_id']}").json()
    assert [r['amount_micros'] for r in older['entries']] == [100] and older['next_before_id'] is None


def test_metrics_report_charges_and_margin(client):
    topup(client)
    reserve(client)
    client.post('/v1/reservations/r1/settle', json=dict(usage=[dict(alias='open-default', input_tokens=1000, output_tokens=1000)]))
    text = client.get('/metrics').text
    assert 'billing_charged_micros_total{action="chat",alias="open-default"}' in text
    assert 'billing_margin_micros_total{alias="open-default"}' in text


def test_closing_an_account_through_the_api(client):
    topup(client)
    reserve(client)
    assert client.post('/v1/accounts/a1/close').status_code == 204
    assert client.post('/v1/accounts/a1/close').status_code == 204
    assert client.get('/v1/accounts/a1/balance').json()['reserved_micros'] == 0
    refused = reserve(client, request_id='r2')
    assert refused.status_code == 403 and refused.json() == {'detail': 'This account has been closed.'}
