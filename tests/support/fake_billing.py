"""In-process fake of the billing service contract (contracts/billing.yaml) for app tests.

Charges 1 micro per token so expectations stay easy to read. Never a pricing oracle.
"""
import json

import httpx


class FakeBilling:
    def __init__(self, available_micros=1_000_000, premium_micros=None):
        self.available = available_micros
        self.purchased = available_micros if premium_micros is None else premium_micros
        self.reservations: dict[str, dict] = {}
        self.calls: list[tuple[str, str, dict]] = []     # (method, path, body)
        self.fail_paths: set[str] = set()                # substrings that return 503
        self.unknown_aliases: set[str] = set()
        self.reserved_amount = 4_000
        self.settled: dict[str, int] = {}
        self.grant_reason = 'already_granted'
        self.closed: set[str] = set()
        self.checkout_status = 200
        self.history_rows = []

    # -- helpers ---------------------------------------------------------
    def paths(self, suffix=''):
        return [p for _, p, _ in self.calls if p.endswith(suffix)]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def client(self):
        return httpx.Client(transport=self.transport(), base_url='http://billing')

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b'{}')
        path = request.url.path
        self.calls.append((request.method, path, body))
        if any(f in path for f in self.fail_paths):
            return httpx.Response(503, json={'detail': 'down'})
        if path == '/v1/packs' and request.url.params.get('channel') == 'store':
            return httpx.Response(200, json={'packs': [dict(id='store-5', usd_cents=499, credits=5000, available=True, product_id='credits_5000'),
                                                       dict(id='store-10', usd_cents=999, credits=10000, available=False)]})
        if path == '/v1/packs':
            return httpx.Response(200, json={'packs': [dict(id='web-5', usd_cents=500, credits=5000, available=True),
                                                       dict(id='web-10', usd_cents=1000, credits=10500, available=False)]})
        if path == '/v1/checkout':
            if self.checkout_status != 200:
                return httpx.Response(self.checkout_status, json={'detail': 'nope'})
            return httpx.Response(200, json=dict(transaction_id='txn_fake', client_token='live_client_token', environment='sandbox'))
        if path.endswith('/history'):
            before = request.url.params.get('before_id')
            rows = [r for r in self.history_rows if before is None or r['id'] < int(before)]
            limit = int(request.url.params.get('limit', 50))
            return httpx.Response(200, json={'entries': rows[:limit], 'next_before_id': rows[limit - 1]['id'] if len(rows) > limit else None})
        if path.endswith('/close'):
            self.closed.add(path.split('/')[3])
            return httpx.Response(204)
        if path == '/v1/reservations' and request.method == 'POST':
            if body['account_id'] in self.closed:
                return httpx.Response(403, json={'detail': 'This account has been closed.'})
            if body['alias'] in self.unknown_aliases:
                return httpx.Response(422, json={'detail': f"No price is published for alias {body['alias']!r}"})
            premium = body['alias'].startswith('premium-')
            pool = self.purchased if premium else self.available
            if pool < self.reserved_amount:
                return httpx.Response(402, json=dict(detail='Not enough credits', balance_micros=self.available,
                                                     required_micros=self.reserved_amount, premium_requires_purchase=premium and self.available >= self.reserved_amount))
            self.available -= self.reserved_amount
            self.reservations[body['request_id']] = dict(body, reserved=self.reserved_amount)
            return httpx.Response(201, json=dict(request_id=body['request_id'], reserved_micros=self.reserved_amount, available_micros=self.available))
        if path.endswith('/settle'):
            rid = path.split('/')[3]
            if rid not in self.reservations:
                return httpx.Response(404, json={'detail': 'Unknown reservation'})
            if rid in self.settled:
                return httpx.Response(200, json=dict(charged_micros=self.settled[rid], written_off_micros=0, available_micros=self.available))
            charge = sum(u['input_tokens'] + u['output_tokens'] for u in body['usage'])
            self.available += self.reservations[rid]['reserved'] - charge
            self.settled[rid] = charge
            return httpx.Response(200, json=dict(charged_micros=charge, written_off_micros=0, available_micros=self.available))
        if path.endswith('/release'):
            rid = path.split('/')[3]
            if rid in self.reservations and rid not in self.settled:
                self.available += self.reservations[rid]['reserved']
                self.settled[rid] = 0
            return httpx.Response(204)
        if path.endswith('/grants/starter'):
            return httpx.Response(200, json={'granted': False, 'reason': self.grant_reason})
        if path.endswith('/balance'):
            return httpx.Response(200, json=dict(available_micros=self.available, reserved_micros=0, starter_micros=0))
        if path == '/v1/estimate':
            return httpx.Response(200, json={'micros': (body['input_tokens'] + body['output_tokens'])})
        return httpx.Response(404)
