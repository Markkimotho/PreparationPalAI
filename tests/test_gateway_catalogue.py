import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import gateway_models
from app.api import app
from app.config import get_base_settings
from app.model_catalog import catalogue, require_model
from tests.support.fake_openai import FakeOpenAI

SERVED = ['open-default', 'open-default-fallback', 'open-fast', 'open-reasoning', 'guard', 'guard-fallback',
          'vision-open', 'embed-default', 'premium-claude', 'premium-claude-fallback']


@pytest.fixture
def gateway(monkeypatch):
    gateway_models.clear_cache()
    with FakeOpenAI() as fake:
        fake.models = list(SERVED)
        settings = get_base_settings()
        monkeypatch.setattr(settings, 'inference_backend', 'gateway')
        monkeypatch.setattr(settings, 'gateway_base_url', fake.url)
        monkeypatch.setattr(settings, 'gateway_api_key', SecretStr('sk-test'))
        monkeypatch.setattr(settings, 'ollama_model', 'open-default')
        yield fake
    gateway_models.clear_cache()


client = TestClient(app)


def test_gateway_catalogue_lists_selectable_aliases_with_tiers(gateway):
    body = client.get('/api/models').json()
    assert [m['id'] for m in body['catalogue']] == ['open-default', 'open-fast', 'open-reasoning', 'premium-claude']
    assert [m['tier'] for m in body['catalogue']] == ['open', 'open', 'open', 'premium']
    assert all(m['installed'] and m['pullable'] is False for m in body['catalogue'])
    assert body['installed'] == sorted(m['id'] for m in body['catalogue'])
    hidden = {'guard', 'guard-fallback', 'vision-open', 'embed-default', 'open-default-fallback', 'premium-claude-fallback'}
    assert hidden.isdisjoint(body['supported'])


def test_self_hosted_catalogue_entries_are_pullable():
    entries = catalogue({'qwen2.5:7b'})
    assert entries and all(m['pullable'] is True and m['tier'] is None for m in entries)


def test_stale_model_preference_returns_409_naming_available_models(gateway):
    r = client.post('/api/chat/stream', json={'question': 'hi', 'model': 'qwen2.5:7b'})
    assert r.status_code == 409
    assert 'open-default' in r.json()['detail'] and 'Pull' not in r.json()['detail']


def test_default_model_is_the_gateway_alias(gateway):
    assert require_model(None) == 'open-default'
    assert require_model('premium-claude') == 'premium-claude'


def test_pull_is_disabled_in_gateway_mode(gateway):
    for path in ('/api/models/pull', '/api/models/pull/stream'):
        r = client.post(path, json={'model': 'open-fast'})
        assert r.status_code == 404
        assert r.json()['detail'] == 'Model downloads are managed by the hosting provider.'


def test_model_list_is_cached_briefly(gateway):
    client.get('/api/models')
    client.get('/api/models')
    assert [p for p in gateway.gets if p.endswith('/models')] == ['/v1/models']


def test_cache_expires(gateway, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(gateway_models.time, 'monotonic', lambda: clock[0])
    assert 'premium-claude' in gateway_models.selectable()
    gateway.models = ['open-default']
    assert 'premium-claude' in gateway_models.selectable()      # still cached
    clock[0] += gateway_models.TTL + 1
    assert gateway_models.selectable() == {'open-default'}


def test_health_reports_gateway_state(gateway, monkeypatch):
    assert client.get('/api/health').json() == {'online': True, 'model_count': 4}
    monkeypatch.setattr(get_base_settings(), 'gateway_base_url', 'http://127.0.0.1:1')
    gateway_models.clear_cache()
    assert client.get('/api/health').json() == {'online': False, 'model_count': 0}


def test_readiness_checks_gateway_chat_and_embedding_alias(gateway, monkeypatch):
    ready = client.get('/health/ready')
    assert ready.json()['dependencies']['gateway'] is True
    assert ready.json()['dependencies']['chat_model'] is True
    assert ready.json()['dependencies']['embedding_model'] is True
    gateway.models = ['open-fast']
    gateway_models.clear_cache()
    deps = client.get('/health/ready').json()['dependencies']
    assert deps['chat_model'] is False and deps['embedding_model'] is False
    assert client.get('/health/ready').status_code == 503


def test_gateway_down_is_empty_not_a_crash(gateway, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'gateway_base_url', 'http://127.0.0.1:1')
    gateway_models.clear_cache()
    assert gateway_models.selectable() == set()
    assert client.get('/api/models').json()['catalogue'] == []
