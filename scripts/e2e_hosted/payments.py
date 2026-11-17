"""Payment scenario: a signed-in learner buys credits, Paddle retries, then refunds part of it.

    python scripts/e2e_hosted/payments.py <issuer.json> <fake-paddle-record.jsonl> <webhook secret>
"""
import hashlib
import hmac
import json
import sys
import time

import httpx

tokens = json.load(open(sys.argv[1]))
record, secret = sys.argv[2], sys.argv[3]
app = httpx.Client(base_url='http://localhost:18000', timeout=30, headers={'Authorization': f"Bearer {tokens['alice']}"})
billing = httpx.Client(base_url='http://localhost:18100', timeout=30)


def show(title, value):
    print(f'\n== {title}\n{value}')


def webhook(event):
    body = json.dumps(event).encode()
    ts = int(time.time())
    signature = hmac.new(secret.encode(), f'{ts}:'.encode() + body, hashlib.sha256).hexdigest()
    return billing.post('/webhooks/paddle', content=body, headers={'Paddle-Signature': f'ts={ts};h1={signature}'})


credits = lambda: app.get('/api/billing/balance').json()['available_credits']
show('1. packs on sale', [(p['id'], p['price'], p['credits'], p['available']) for p in app.get('/api/billing/packs').json()['packs']])
before = credits()
show('   balance before buying', before)
checkout = app.post('/api/billing/checkout', json={'pack': 'web-10', 'account_id': 'someone-else'}).json()
show('2. checkout started (client tried to name another account)', checkout)
sent = [json.loads(line) for line in open(record)][-1]
show('   what billing asked Paddle for', sent)
account = sent['request']['custom_data']['account_id']
me = app.get('/api/auth/me').json()['workspace']
show('   tagged with the signed-in learner, not the requested one', account == me)

paid = {'event_id': 'evt_1', 'event_type': 'transaction.completed', 'data': {
    'id': checkout['transaction_id'], 'status': 'completed', 'currency_code': 'USD', 'custom_data': sent['request']['custom_data'],
    'items': [{'price': {'id': sent['request']['items'][0]['price_id']}, 'quantity': 1}], 'details': {'totals': {'grand_total': '1000'}}}}
show('3. Paddle confirms payment, then retries four times', [webhook(paid).json()['outcome'] for _ in range(5)])
show('   balance after', (credits(), credits() - before))
forged = json.dumps(paid | {'data': paid['data'] | {'id': 'txn_forged'}}).encode()
show('4. a forged notification (bad signature)', billing.post('/webhooks/paddle', content=forged,
     headers={'Paddle-Signature': f'ts={int(time.time())};h1={"0" * 64}'}).status_code)
refund = {'event_id': 'evt_2', 'event_type': 'adjustment.created', 'data': {'id': 'adj_1', 'action': 'refund', 'status': 'approved',
          'transaction_id': checkout['transaction_id'], 'totals': {'total': '500', 'currency_code': 'USD'}}}
show('5. half the purchase is refunded (delivered twice)', [webhook(refund).json()['outcome'] for _ in range(2)])
show('   balance after the refund', (credits(), credits() - before))
show('6. history the learner sees', [(e['label'], e['credits']) for e in app.get('/api/billing/history').json()['entries']])
