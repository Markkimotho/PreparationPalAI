import base64
import hashlib
import hmac
import json
import re
import time

import pytest
from pydantic import SecretStr

from app import oidc
from app.config import get_base_settings
from app.oidc import TokenRejected, verify_token, workspace_for
from tests.support.fake_issuer import FakeIssuer


@pytest.fixture
def issuer(monkeypatch):
    fake = FakeIssuer()
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'auth_mode', 'oidc')
    monkeypatch.setattr(settings, 'oidc_issuer', fake.issuer)
    monkeypatch.setattr(settings, 'oidc_audience', fake.audience)
    monkeypatch.setattr(settings, 'oidc_jwks_url', fake.jwks_url)
    oidc.reset_cache()
    clock = [1000.0]
    monkeypatch.setattr(oidc, 'clock', lambda: clock[0])
    fake.clock = clock
    yield fake
    fake.close()
    oidc.reset_cache()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def forged(header: dict, claims: dict, secret: bytes | None = None) -> str:
    head, body = b64(json.dumps(header).encode()), b64(json.dumps(claims).encode())
    signature = b64(hmac.new(secret, f'{head}.{body}'.encode(), hashlib.sha256).digest()) if secret else ''
    return f'{head}.{body}.{signature}'


def test_valid_token_maps_to_a_stable_private_workspace(issuer):
    principal = verify_token(issuer.sign(sub='user-1'))
    assert principal.workspace == workspace_for(issuer.issuer, 'user-1') == verify_token(issuer.sign(sub='user-1')).workspace
    assert re.fullmatch(r'u-[0-9a-f]{20}', principal.workspace)
    assert principal.workspace != verify_token(issuer.sign(sub='user-2')).workspace
    assert (principal.email, principal.email_verified, principal.subject) == ('learner@example.com', True, 'user-1')


def test_workspace_id_never_contains_the_email_or_subject(issuer):
    principal = verify_token(issuer.sign(sub='secret-sub', email='someone@example.com'))
    assert 'someone' not in principal.workspace and 'secret' not in principal.workspace


def test_roles_claim_defaults_to_editor_and_picks_the_highest(issuer):
    assert verify_token(issuer.sign()).role == 'editor'
    assert verify_token(issuer.sign(roles=['reader'])).role == 'reader'
    assert verify_token(issuer.sign(roles=['reader', 'admin'])).role == 'admin'
    assert verify_token(issuer.sign(roles='admin')).role == 'admin'
    assert verify_token(issuer.sign(roles=['nonsense'])).role == 'editor'


def test_unverified_email_is_reported_as_unverified(issuer):
    assert verify_token(issuer.sign(email_verified='true')).email_verified is False       # only a real boolean counts
    assert verify_token(issuer.sign(email_verified=False)).email_verified is False


@pytest.mark.parametrize('name,build', [
    ('expired', lambda i: i.sign(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200)),
    ('not yet valid', lambda i: i.sign(nbf=int(time.time()) + 3600)),
    ('wrong issuer', lambda i: i.sign(iss='https://evil.example/oidc')),
    ('wrong audience', lambda i: i.sign(aud='https://other-api.example')),
    ('missing subject', lambda i: i.sign({k: v for k, v in i.claims().items() if k != 'sub'})),
    ('missing expiry', lambda i: i.sign({k: v for k, v in i.claims().items() if k != 'exp'})),
    ('alg none', lambda i: forged({'alg': 'none', 'typ': 'JWT'}, i.claims())),
    ('hs256 with the public key as secret', lambda i: forged({'alg': 'HS256', 'typ': 'JWT', 'kid': next(iter(i.keys))}, i.claims(), i.public_pem())),
    ('tampered payload', lambda i: (lambda t: '.'.join([t.split('.')[0], b64(json.dumps(i.claims(sub='admin')).encode()), t.split('.')[2]]))(i.sign())),
    ('garbage', lambda i: 'not.a.jwt'),
    ('empty', lambda i: ''),
])
def test_rejected_tokens(issuer, name, build):
    with pytest.raises(TokenRejected):
        verify_token(build(issuer))


def test_ten_seconds_of_clock_skew_is_tolerated(issuer):
    verify_token(issuer.sign(exp=int(time.time()) - 10, iat=int(time.time()) - 700))


def test_unknown_kid_refetches_once_then_accepts_after_rotation(issuer):
    verify_token(issuer.sign())
    before = issuer.fetches
    new_kid = issuer.rotate()
    issuer.clock[0] += 60
    assert verify_token(issuer.sign(kid=new_kid)).subject == 'user-1'
    assert issuer.fetches == before + 1


def test_unknown_kid_is_rejected_when_a_refetch_does_not_help(issuer):
    verify_token(issuer.sign())
    issuer.clock[0] += 60          # a refetch is allowed, and it still finds no such key
    stranger = FakeIssuer()
    try:
        with pytest.raises(TokenRejected):
            verify_token(stranger.sign(stranger.claims() | {'iss': issuer.issuer, 'aud': issuer.audience}))
    finally:
        stranger.close()


def test_refetch_is_rate_limited(issuer):
    verify_token(issuer.sign())
    issuer.clock[0] += 60
    before = issuer.fetches
    attacker = FakeIssuer()
    try:
        for _ in range(10):
            with pytest.raises(TokenRejected):
                verify_token(attacker.sign(attacker.claims() | {'iss': issuer.issuer, 'aud': issuer.audience}))
    finally:
        attacker.close()
    assert issuer.fetches - before == 1      # ten forged key ids cause exactly one refetch


def test_cached_keys_survive_a_jwks_outage_for_a_day_and_no_longer(issuer):
    token = issuer.sign(exp=int(time.time()) + 10 * 86400, iat=int(time.time()))
    verify_token(token)
    issuer.down = True
    issuer.clock[0] += 23 * 3600
    assert verify_token(token).subject == 'user-1'
    issuer.clock[0] += 2 * 3600
    with pytest.raises(TokenRejected):
        verify_token(token)


def test_first_use_with_the_issuer_down_rejects_instead_of_trusting(issuer):
    issuer.down = True
    with pytest.raises(TokenRejected):
        verify_token(issuer.sign())


def test_rejection_reasons_never_contain_the_token(issuer):
    token = issuer.sign(iss='https://evil.example/oidc')
    with pytest.raises(TokenRejected) as caught:
        verify_token(token)
    assert token not in caught.value.reason and token.split('.')[1] not in caught.value.reason
