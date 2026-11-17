"""Verify OIDC access tokens and map each signed-in learner to a private workspace.

Rules (each is tested in tests/test_oidc.py):
  * Only RS256 and ES256 are accepted, never `none` or any HMAC algorithm.
  * Issuer, audience, subject, issued-at and expiry must all be present and correct (60s leeway).
  * Signing keys come from the issuer's JWKS. An unknown key id triggers one refetch, at most
    every 30 seconds. Keys refresh every 10 minutes, and if the issuer is unreachable cached keys
    keep working for 24 hours, after which tokens are rejected rather than trusted blindly.
  * The workspace id is a one-way hash of issuer and subject, never the email address.
"""
import hashlib
import threading
from dataclasses import dataclass

import httpx
import jwt

from app.config import get_base_settings

ALGORITHMS = ('RS256', 'ES256')
LEEWAY = 60
REFRESH = 600
REFETCH_MIN = 30
MAX_STALE = 86400
RANK = {'reader': 1, 'editor': 2, 'admin': 3}

import time as _time

clock = _time.monotonic     # replaced in tests
_lock = threading.Lock()
_state: dict = {'keys': {}, 'fetched_at': None, 'attempt_at': None}


class TokenRejected(Exception):
    """The token is not acceptable. `reason` is short, generic and safe to log (never the token)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Principal:
    workspace: str
    identity: str
    role: str
    email: str | None
    email_verified: bool
    subject: str


def reset_cache() -> None:
    with _lock:
        _state.update(keys={}, fetched_at=None, attempt_at=None)


def workspace_for(issuer: str, subject: str) -> str:
    return 'u-' + hashlib.sha256(f'{issuer}|{subject}'.encode()).hexdigest()[:20]


def _fetch() -> None:
    settings = get_base_settings()
    url = settings.oidc_jwks_url or settings.oidc_issuer.rstrip('/') + '/jwks'
    _state['attempt_at'] = clock()
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
        keys = {}
        for jwk in response.json()['keys']:
            if jwk.get('kid') and jwk.get('kty') in ('RSA', 'EC'):
                keys[jwk['kid']] = jwt.PyJWK.from_dict(jwk).key
    except (httpx.HTTPError, ValueError, KeyError, jwt.PyJWTError):
        return                                   # keep whatever is cached; MAX_STALE bounds how long
    _state.update(keys=keys, fetched_at=clock())


def _key_for(kid: str):
    with _lock:
        now = clock()
        if _state['fetched_at'] is not None and now - _state['fetched_at'] > MAX_STALE:
            _state.update(keys={}, fetched_at=None)
        need = _state['fetched_at'] is None or kid not in _state['keys'] or now - _state['fetched_at'] > REFRESH
        may = _state['attempt_at'] is None or now - _state['attempt_at'] >= REFETCH_MIN
        if need and may:
            _fetch()
        return _state['keys'].get(kid)


def _role(claim) -> str:
    names = [claim] if isinstance(claim, str) else claim if isinstance(claim, list) else []
    known = [n for n in names if n in RANK]
    return max(known, key=RANK.get) if known else 'editor'


def verify_token(token: str) -> Principal:
    settings = get_base_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise TokenRejected('malformed') from None
    if header.get('alg') not in ALGORITHMS:
        raise TokenRejected('algorithm')
    kid = header.get('kid')
    if not isinstance(kid, str):
        raise TokenRejected('no key id')
    key = _key_for(kid)
    if key is None:
        raise TokenRejected('unknown key')
    try:
        claims = jwt.decode(token, key, algorithms=[header['alg']], audience=settings.oidc_audience,
                            issuer=settings.oidc_issuer, leeway=LEEWAY, options={'require': ['exp', 'iat', 'sub']})
    except jwt.PyJWTError as exc:
        raise TokenRejected(type(exc).__name__) from None
    subject = claims['sub']
    if not isinstance(subject, str) or not subject:
        raise TokenRejected('subject')
    workspace = workspace_for(settings.oidc_issuer, subject)
    return Principal(workspace=workspace, identity=workspace, role=_role(claims.get('roles')),
                     email=claims.get('email') if isinstance(claims.get('email'), str) else None,
                     email_verified=claims.get('email_verified') is True, subject=subject)
