"""A fake OIDC issuer for tests: generates keys (RSA by default, EC like Logto's ES384 on request), serves a JWKS, signs tokens."""
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

CURVES = {'ES256': ec.SECP256R1, 'ES384': ec.SECP384R1}


_POOL: list[rsa.RSAPrivateKey] = []     # RSA generation is slow; reuse a few keys across tests
_NEXT = [0]


def _next_key() -> rsa.RSAPrivateKey:
    while len(_POOL) < 8:
        _POOL.append(rsa.generate_private_key(public_exponent=65537, key_size=2048))
    _NEXT[0] += 1
    return _POOL[_NEXT[0] % len(_POOL)]


class FakeIssuer:
    def __init__(self, audience='https://api.preparationpal.test', alg='RS256'):
        self.audience = audience
        self.alg = alg                  # Logto's default is ES384 (EC P-384)
        self.fetches = 0
        self.down = False
        self.keys: dict = {}
        self.add_key()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                outer.fetches += 1
                if outer.down:
                    self.send_response(503)
                    self.end_headers()
                    return
                body = json.dumps({'keys': outer.jwks()}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True).start()

    @property
    def issuer(self) -> str:
        return f'http://127.0.0.1:{self.server.server_address[1]}/oidc'

    @property
    def jwks_url(self) -> str:
        return f'http://127.0.0.1:{self.server.server_address[1]}/oidc/jwks'

    def add_key(self) -> str:
        kid = uuid.uuid4().hex[:8]
        self.keys[kid] = ec.generate_private_key(CURVES[self.alg]()) if self.alg in CURVES else _next_key()
        return kid

    def rotate(self) -> str:
        """Replace every signing key with a new one (the old kid disappears from the JWKS)."""
        self.keys.clear()
        return self.add_key()

    def jwks(self) -> list[dict]:
        keys = []
        for kid, key in self.keys.items():
            algorithm = jwt.algorithms.ECAlgorithm if self.alg in CURVES else jwt.algorithms.RSAAlgorithm
            jwk = json.loads(algorithm.to_jwk(key.public_key()))
            keys.append(dict(jwk, kid=kid, use='sig', alg=self.alg))
        return keys

    def public_pem(self, kid: str | None = None) -> bytes:
        key = self.keys[kid or next(iter(self.keys))]
        return key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def claims(self, sub='user-1', **overrides) -> dict:
        now = int(time.time())
        return {'iss': self.issuer, 'aud': self.audience, 'sub': sub, 'iat': now, 'exp': now + 600,
                'email': 'learner@example.com', 'email_verified': True} | overrides

    def sign(self, claims: dict | None = None, kid: str | None = None, **claim_overrides) -> str:
        kid = kid or next(iter(self.keys))
        payload = (claims if claims is not None else self.claims()) | claim_overrides
        return jwt.encode(payload, self.keys[kid], algorithm=self.alg, headers={'kid': kid})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
