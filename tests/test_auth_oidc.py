import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import oidc
from app.api import app
from app.config import Settings, get_base_settings
from tests.support.fake_issuer import FakeIssuer

client = TestClient(app)


@pytest.fixture
def issuer(tmp_path, monkeypatch):
    fake = FakeIssuer()
    settings = get_base_settings()
    for name, value in dict(auth_mode='oidc', auth_enabled=True, oidc_issuer=fake.issuer, oidc_audience=fake.audience,
                            oidc_jwks_url=fake.jwks_url, flashcards_dir=str(tmp_path / 'cards'),
                            auth_tokens={}).items():
        monkeypatch.setattr(settings, name, value)
    oidc.reset_cache()
    yield fake
    fake.close()
    oidc.reset_cache()


def bearer(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


def test_signed_in_learner_gets_a_private_workspace(issuer):
    me = client.get('/api/auth/me', headers=bearer(issuer.sign(sub='alice'))).json()
    assert me['workspace'] == oidc.workspace_for(issuer.issuer, 'alice') and me['email_verified'] is True and me['mode'] == 'oidc'


def test_missing_token_is_a_plain_401(issuer):
    r = client.get('/api/flashcards')
    assert r.status_code == 401 and r.headers['www-authenticate'] == 'Bearer'


@pytest.mark.parametrize('token', ['garbage', 'a.b.c'])
def test_bad_tokens_get_invalid_token_and_no_reason(issuer, token):
    r = client.get('/api/flashcards', headers=bearer(token))
    assert r.status_code == 401 and r.headers['www-authenticate'] == 'Bearer error="invalid_token"'
    assert r.json() == {'detail': 'Sign in to continue.'}


def test_expired_token_is_rejected(issuer):
    import time
    token = issuer.sign(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200)
    assert client.get('/api/flashcards', headers=bearer(token)).status_code == 401


def test_two_learners_cannot_see_each_others_data(issuer):
    alice, bob = bearer(issuer.sign(sub='alice')), bearer(issuer.sign(sub='bob'))
    assert client.post('/api/flashcards', json={'name': 'Alice private'}, headers=alice).status_code == 200
    assert [d['name'] for d in client.get('/api/flashcards', headers=alice).json()['decks']] == ['Alice private']
    assert client.get('/api/flashcards', headers=bob).json()['decks'] == []


def test_reader_role_cannot_change_data(issuer):
    reader = bearer(issuer.sign(roles=['reader']))
    assert client.get('/api/flashcards', headers=reader).status_code == 200
    assert client.post('/api/flashcards', json={'name': 'x'}, headers=reader).status_code == 403


def test_metrics_and_model_pulls_are_admin_only(issuer):
    editor, admin = bearer(issuer.sign()), bearer(issuer.sign(roles=['admin']))
    assert client.get('/metrics', headers=editor).status_code == 403
    assert client.get('/metrics', headers=admin).status_code == 200
    assert client.post('/api/models/pull', json={'model': 'x'}, headers=editor).status_code == 403


def test_status_tells_clients_where_to_sign_in_without_a_token(issuer):
    body = client.get('/api/auth/status').json()
    assert body == {'enabled': True, 'mode': 'oidc', 'issuer': issuer.issuer}


def test_token_mode_is_unchanged(monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'auth_mode', 'tokens')
    monkeypatch.setattr(settings, 'auth_enabled', False)
    assert client.get('/api/auth/status').json() == {'enabled': False, 'mode': 'tokens', 'issuer': None}
    assert client.get('/api/auth/me').json()['workspace'] == 'local'


def make(**kw):
    return Settings(_env_file=None, **kw)


def test_oidc_mode_needs_an_issuer_and_audience_and_turns_auth_on():
    with pytest.raises(ValidationError, match='OIDC_ISSUER'):
        make(auth_mode='oidc', oidc_audience='https://api.example')
    with pytest.raises(ValidationError, match='OIDC_AUDIENCE'):
        make(auth_mode='oidc', oidc_issuer='https://id.example/oidc')
    s = make(auth_mode='oidc', oidc_issuer='https://id.example/oidc', oidc_audience='https://api.example')
    assert s.auth_enabled is True


def test_oidc_issuer_must_be_a_plain_https_or_http_origin_url():
    for bad in ('ftp://id.example', 'https://u:p@id.example', 'id.example/oidc'):
        with pytest.raises(ValidationError):
            make(auth_mode='oidc', oidc_issuer=bad, oidc_audience='a')


def test_production_with_oidc_is_allowed_without_static_tokens():
    make(auth_mode='oidc', oidc_issuer='https://id.example/oidc', oidc_audience='a', production=True, cors_origins=['https://app.example'])
