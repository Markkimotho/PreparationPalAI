import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import billing_client, billing_outbox, metered
from app.api import app
from app.config import get_base_settings
from app.llm import ModelServiceUnavailable
from app.metering import UsageRecord, record
from tests.support.fake_billing import FakeBilling


def usage(alias='open-default', purpose='main', i=100, o=50):
    return UsageRecord(alias, purpose, i, o, False)


@pytest.fixture
def billing(tmp_path, monkeypatch):
    settings = get_base_settings()
    fake = FakeBilling()
    monkeypatch.setattr(settings, 'billing_enabled', True)
    monkeypatch.setattr(settings, 'billing_outbox_db', str(tmp_path / 'outbox.sqlite3'))
    monkeypatch.setattr(settings, 'top_up_url', 'https://pay.example/top-up')
    monkeypatch.setattr(settings, 'inference_backend', 'gateway')
    monkeypatch.setattr(settings, 'ollama_model', 'open-default')
    monkeypatch.setattr(metered, 'get_client', lambda: billing_client.BillingClient(client=fake.client()))
    metered._started.clear()
    monkeypatch.setattr('app.model_catalog.get_installed_models', lambda: {'open-default', 'open-fast', 'premium-claude'})
    yield fake


client = TestClient(app)


def post_chat(**body):
    return client.post('/api/chat/stream', json={'question': 'hi', **body})


def engine(*records, tokens=('ok',), error=None):
    def run(**_kwargs):
        for r in records:
            record(r)
        if error:
            raise error
        for t in tokens:
            yield 'token', t
    return run


def test_disabled_billing_makes_no_billing_calls(billing, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'billing_enabled', False)
    from unittest.mock import patch
    with patch('app.api.lcel_chain.stream', side_effect=engine(usage())):
        assert post_chat().status_code == 200
    assert billing.calls == []


def test_a_model_route_reserves_then_settles_the_real_usage(billing):
    from unittest.mock import patch
    with patch('app.api.lcel_chain.stream', side_effect=engine(usage(i=120, o=30), usage('guard', 'guard', 40, 5))):
        response = post_chat()
    assert response.status_code == 200 and '"type": "token"' in response.text
    reserve = next(b for m, p, b in billing.calls if p == '/v1/reservations')
    assert reserve['alias'] == 'open-default' and reserve['action'] == 'chat' and reserve['account_id'] == 'local'
    assert {l['alias'] for l in reserve['lines']} == {'open-default', 'guard'}
    settle = next(b for m, p, b in billing.calls if p.endswith('/settle'))
    assert sorted((u['alias'], u['input_tokens'], u['output_tokens']) for u in settle['usage']) == [('guard', 40, 5), ('open-default', 120, 30)]
    assert billing.available == 1_000_000 - 195


def test_402_has_the_documented_shape(billing):
    billing.available = 1_000
    response = post_chat()
    assert response.status_code == 402
    assert response.json() == {'detail': 'Not enough credits for this action.', 'balance_credits': 1,
                               'required_credits': 4, 'top_up_url': 'https://pay.example/top-up'}
    assert billing.paths('/settle') == [] and billing.paths('/release') == []


def test_premium_with_only_free_credits_explains_itself(billing):
    billing.purchased = 0
    response = post_chat(model='premium-claude')
    assert response.status_code == 402 and 'Premium models use purchased credits' in response.json()['detail']


def test_unpriced_model_never_reaches_inference(billing):
    from unittest.mock import patch
    billing.unknown_aliases = {'open-fast'}
    with patch('app.api.lcel_chain.stream') as stream:
        response = post_chat(model='open-fast')
    assert response.status_code == 409 and 'open-fast' in response.json()['detail']
    stream.assert_not_called()


def test_failed_model_call_releases_the_hold(billing):
    from unittest.mock import patch
    with patch('app.api.lcel_chain.stream', side_effect=engine(error=ModelServiceUnavailable())):
        response = post_chat()
    assert 'The model service is unavailable' in response.text
    assert billing.paths('/release') and billing.paths('/settle') == []
    assert billing.available == 1_000_000


def test_billing_down_at_reserve_fails_closed(billing):
    from unittest.mock import patch
    billing.fail_paths = {'/v1/reservations'}
    with patch('app.api.lcel_chain.stream') as stream:
        response = post_chat()
    assert response.status_code == 503 and 'Billing is temporarily unavailable' in response.json()['detail']
    stream.assert_not_called()


def test_billing_down_at_settle_keeps_the_usage_and_flushes_later(billing):
    from unittest.mock import patch
    billing.fail_paths = {'/settle'}
    with patch('app.api.lcel_chain.stream', side_effect=engine(usage(i=80, o=20))):
        assert post_chat().status_code == 200
    assert billing_outbox.pending() == 1
    billing.fail_paths = set()
    assert billing_outbox.flush(billing_client.BillingClient(client=billing.client())) == 1
    assert billing_outbox.pending() == 0 and sum(billing.settled.values()) == 100
    assert billing_outbox.flush(billing_client.BillingClient(client=billing.client())) == 0


def test_runaway_actions_are_stopped_and_still_charged(billing):
    from unittest.mock import patch
    runaway = engine(usage(), usage(), usage())     # chat reserves two main calls: rephrase, then answer
    with patch('app.api.lcel_chain.stream', side_effect=runaway):
        response = post_chat()
    assert 'more model steps than allowed' in response.text
    settle = next(b for m, p, b in billing.calls if p.endswith('/settle'))
    assert sum(u['input_tokens'] for u in settle['usage']) == 300      # two allowed calls plus the one that crossed the line


def test_a_chat_with_history_may_rephrase_then_answer(billing):
    """Found by the live end-to-end run: with chat history the RAG chain makes two model calls."""
    from unittest.mock import patch
    with patch('app.api.lcel_chain.stream', side_effect=engine(usage('open-default', 'main', 90, 10), usage('open-default', 'main', 300, 40))):
        response = post_chat()
    assert 'more model steps than allowed' not in response.text and '"type": "token"' in response.text
    reserve = next(b for m, p, b in billing.calls if p == '/v1/reservations')
    assert next(l for l in reserve['lines'] if l['alias'] == 'open-default')['calls'] == 2


def test_langgraph_chat_has_the_same_allowance(billing):
    from unittest.mock import patch
    with patch('app.api.langgraph_module.stream', side_effect=engine(usage(), usage())):
        response = post_chat(mode='langgraph')
    assert 'more model steps than allowed' not in response.text


def test_client_disconnect_still_settles_what_was_used(billing):
    scope = {'type': 'http', 'method': 'POST', 'path': '/api/chat/stream', 'headers': [(b'content-type', b'application/json')],
             'query_string': b'', 'raw_path': b'/api/chat/stream'}
    sent = []

    async def downstream(scope, receive, send):
        record(usage(i=70, o=10))
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'data: x\n\n', 'more_body': True})
        raise asyncio.CancelledError          # the client went away mid-stream

    async def receive():
        return {'type': 'http.request', 'body': b'{"question": "hi"}', 'more_body': False}

    async def send(message):
        sent.append(message)

    async def run():
        with pytest.raises(asyncio.CancelledError):
            await metered.BillingMiddleware(downstream)(scope, receive, send)

    asyncio.run(run())
    assert billing.paths('/settle') and sum(billing.settled.values()) == 80


def test_unmetered_routes_are_untouched(billing):
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/flashcards').status_code == 200
    assert billing.calls == []


def test_balance_and_estimate_endpoints(billing):
    assert client.get('/api/billing/balance').json() == {'available_credits': 1000, 'reserved_credits': 0, 'starter_credits': 0,
                                                         'top_up_url': 'https://pay.example/top-up'}
    estimate = client.get('/api/billing/estimate', params={'action': 'chat', 'model': 'open-default'}).json()
    assert estimate['credits'] >= 1
    assert client.get('/api/billing/estimate', params={'action': 'nope', 'model': 'open-default'}).status_code == 404


def test_every_post_route_is_metered_or_explicitly_exempt():
    posts = {r.path for r in app.routes if 'POST' in getattr(r, 'methods', ())}
    unclassified = [p for p in posts if not metered.is_metered('POST', p) and not metered.is_exempt('POST', p)]
    assert unclassified == [], f'Decide whether these model routes are metered: {unclassified}'


# ---- background ingestion worker -------------------------------------------------------

def test_worker_meters_embedding_work_for_the_jobs_workspace(billing):
    from unittest.mock import patch
    from langchain_core.documents import Document
    from app.jobs import enqueue, get_job, run_once

    def fake_ingest(docs):
        record(UsageRecord('embed-default', 'embed', 900, 0, False))
        return len(docs)

    token = metered.workspace_id.set('class-a')
    try:
        job = enqueue('scrape', dict(topic='physics', num_results=1))
    finally:
        metered.workspace_id.reset(token)
    with patch('app.scraper.search_and_scrape', return_value=[Document(page_content='fact', metadata=dict(id='a'))]), \
         patch('app.vectorstore.ingest_documents', side_effect=fake_ingest):
        assert run_once()
    token = metered.workspace_id.set('class-a')
    try:
        assert get_job(job['id'])['state'] == 'completed'
    finally:
        metered.workspace_id.reset(token)
    reserve = next(b for m, p, b in billing.calls if p == '/v1/reservations')
    assert reserve['account_id'] == 'class-a' and reserve['action'] == 'kb_scrape'
    settle = next(b for m, p, b in billing.calls if p.endswith('/settle'))
    assert settle['usage'] == [dict(alias='embed-default', input_tokens=900, output_tokens=0)]


def test_worker_job_fails_clearly_when_credits_are_short(billing):
    from unittest.mock import patch
    from app.jobs import enqueue, get_job, run_once
    billing.available = 100
    job = enqueue('scrape', dict(topic='physics', num_results=1))
    with patch('app.scraper.search_and_scrape') as scrape:
        run_once()
    result = get_job(job['id'])
    assert result['state'] == 'failed' and 'credits' in result['error'].lower()
    scrape.assert_not_called()


def test_worker_job_fails_closed_when_billing_is_down(billing):
    from unittest.mock import patch
    from app.jobs import enqueue, get_job, run_once
    billing.fail_paths = {'/v1/reservations'}
    job = enqueue('scrape', dict(topic='physics', num_results=1))
    with patch('app.scraper.search_and_scrape') as scrape:
        run_once()
    assert get_job(job['id'])['state'] == 'failed'
    scrape.assert_not_called()


# ---- starter allowance needs a verified email ---------------------------------------------

def grant_calls(billing):
    return [b for m, p, b in billing.calls if p.endswith('/grants/starter')]


def test_the_learners_verified_email_is_sent_with_the_grant_request(billing):
    from app.workspace import account_email, email_verified
    billing.grant_reason = 'granted'
    tokens = account_email.set('Learner@Example.com'), email_verified.set(True)
    try:
        metered._ensure_started(billing_client.BillingClient(client=billing.client()), 'u-abc')
    finally:
        account_email.reset(tokens[0]); email_verified.reset(tokens[1])
    assert grant_calls(billing) == [{'email': 'Learner@Example.com', 'email_verified': True}]


def test_an_unverified_learner_is_asked_again_after_verifying(billing):
    from app.workspace import account_email, email_verified
    client = billing_client.BillingClient(client=billing.client())
    billing.grant_reason = 'email_unverified'
    metered._ensure_started(client, 'u-abc')
    metered._ensure_started(client, 'u-abc')
    assert len(grant_calls(billing)) == 2                       # not cached while unsettled
    billing.grant_reason = 'granted'
    token = email_verified.set(True)
    try:
        metered._ensure_started(client, 'u-abc')
        metered._ensure_started(client, 'u-abc')
    finally:
        email_verified.reset(token)
    assert len(grant_calls(billing)) == 3                       # settled once, then cached


def test_a_refused_duplicate_mailbox_is_not_asked_again(billing):
    client = billing_client.BillingClient(client=billing.client())
    billing.grant_reason = 'email_in_use'
    metered._ensure_started(client, 'u-dup')
    metered._ensure_started(client, 'u-dup')
    assert len(grant_calls(billing)) == 1
