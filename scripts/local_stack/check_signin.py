"""Prove sign-in works end to end against the real local Logto, the way the phone app does it.

Registers (or signs in) a username/password account through Logto's Experience API, completes the
authorization-code + PKCE flow for the native app with the API resource, exchanges the code for an
access token, then calls the Tayarishe server with it. Passes only if the server accepts the
token and reports the account's balance (500 free credits for a new account).

    .venv/bin/python scripts/local_stack/check_signin.py [--username demo --password '...']

Exit code 0 means every step worked; each step prints what it saw.
"""
import argparse
import base64
import hashlib
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

STATE = Path(__file__).with_name('.state')
LOGTO = 'https://localhost:8443'
API = 'http://localhost:18000'
CLIENT_ID = 'ppal-native-local'
REDIRECT = 'tayarishe://auth/callback'
RESOURCE = 'https://api.tayarishe.local'


def fail(step: str, response: httpx.Response | None = None) -> None:
    detail = f' -> {response.status_code} {response.text[:300]}' if response is not None else ''
    sys.exit(f'FAIL {step}{detail}')


def follow_to_callback(client: httpx.Client, location: str) -> str:
    """Follow Logto's redirects until it sends the browser back to the app with a code."""
    for _ in range(10):
        if location.startswith(REDIRECT):
            return location
        response = client.get(location if location.startswith('http') else LOGTO + location)
        if response.status_code not in (302, 303):
            fail(f'redirect chain stopped at {location}', response)
        location = response.headers['location']
    fail('too many redirects')


def experience(client: httpx.Client, username: str, password: str) -> str:
    """Register the account, or sign in if it already exists. Returns where Logto redirects next."""
    r = client.put(f'{LOGTO}/api/experience', json={'interactionEvent': 'Register'})
    r.status_code < 300 or fail('start registration', r)
    r = client.post(f'{LOGTO}/api/experience/profile', json={'type': 'username', 'value': username})
    if r.status_code == 422 and r.json().get('code') == 'user.username_already_in_use':   # registered: sign in instead
        r = client.put(f'{LOGTO}/api/experience', json={'interactionEvent': 'SignIn'})
        r.status_code < 300 or fail('start sign-in', r)
        r = client.post(f'{LOGTO}/api/experience/verification/password',
                        json={'identifier': {'type': 'username', 'value': username}, 'password': password})
        r.status_code < 300 or fail('check password', r)
        r = client.post(f'{LOGTO}/api/experience/identification', json={'verificationId': r.json()['verificationId']})
        r.status_code < 300 or fail('identify', r)
        print(f'ok  signed in existing account {username!r}')
    else:
        r.status_code < 300 or fail('set username', r)
        r = client.post(f'{LOGTO}/api/experience/profile', json={'type': 'password', 'value': password})
        r.status_code < 300 or fail('set password', r)
        r = client.post(f'{LOGTO}/api/experience/identification', json={})
        r.status_code < 300 or fail('create account', r)
        print(f'ok  registered new account {username!r}')
    r = client.post(f'{LOGTO}/api/experience/submit')
    r.status_code < 300 or fail('submit', r)
    return r.json()['redirectTo']


def sign_in(client: httpx.Client, username: str, password: str) -> dict:
    """Run the app's sign-in (authorization code + PKCE) for this account and return Logto's tokens."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    r = client.get(f'{LOGTO}/oidc/auth', params={
        'client_id': CLIENT_ID, 'redirect_uri': REDIRECT, 'response_type': 'code', 'prompt': 'consent',
        'scope': 'openid offline_access profile email roles', 'resource': RESOURCE,
        'code_challenge': challenge, 'code_challenge_method': 'S256', 'state': secrets.token_hex(8)})
    r.status_code in (302, 303) or fail('authorization request', r)
    client.get(LOGTO + r.headers['location'] if r.headers['location'].startswith('/') else r.headers['location'])
    callback = follow_to_callback(client, experience(client, username, password))
    code = parse_qs(urlsplit(callback).query).get('code', [None])[0] or fail(f'no code in {callback}')
    print('ok  Logto redirected back to the app with a code')
    r = client.post(f'{LOGTO}/oidc/token', data={
        'grant_type': 'authorization_code', 'code': code, 'code_verifier': verifier,
        'client_id': CLIENT_ID, 'redirect_uri': REDIRECT, 'resource': RESOURCE})
    r.status_code == 200 or fail('token exchange', r)
    return r.json()


def local_client() -> httpx.Client:
    return httpx.Client(verify=str(STATE / 'local-root.crt'), follow_redirects=False, timeout=20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default=f'check-{secrets.token_hex(3)}')
    parser.add_argument('--password', default=secrets.token_urlsafe(12) + 'aA1!')
    args = parser.parse_args()
    with local_client() as client:
        status = httpx.get(f'{API}/api/auth/status').json()
        native = status.get('native') or {}
        if native != {'endpoint': LOGTO, 'client_id': CLIENT_ID, 'resource': RESOURCE}:
            sys.exit(f'FAIL server publishes the wrong sign-in config: {native}')
        print(f'ok  server publishes sign-in config {native}')
        tokens = sign_in(client, args.username, args.password)
        header = tokens['access_token'].split('.')[0]
        alg = httpx.Response(200, content=base64.urlsafe_b64decode(header + '=' * (-len(header) % 4))).json()['alg']
        print(f'ok  access token issued ({alg}), refresh token {"present" if tokens.get("refresh_token") else "MISSING"}')
        r = httpx.get(f'{API}/api/billing/balance', headers={'Authorization': f'Bearer {tokens["access_token"]}'})
        r.status_code == 200 or fail('server rejected the token', r)
        print(f'ok  server accepted the token; balance {r.json()}')
        if tokens.get('refresh_token'):
            r = client.post(f'{LOGTO}/oidc/token', data={'grant_type': 'refresh_token', 'refresh_token': tokens['refresh_token'],
                                                         'client_id': CLIENT_ID, 'resource': RESOURCE})
            r.status_code == 200 or fail('refresh', r)
            print('ok  refresh token renews the access token')
    print(f'\nPASS  username: {args.username}  password: {args.password}')


if __name__ == '__main__':
    main()
