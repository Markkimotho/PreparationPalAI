"""Paddle (merchant of record): create checkouts and apply signed webhook events to the ledger.

Signature scheme (developer.paddle.com/webhooks/signature-verification): header
`Paddle-Signature: ts=<unix>;h1=<hex>[;h1=<hex>]`, HMAC-SHA256 over `<ts>:<raw body>` with the
notification destination's secret. Any matching h1 is accepted (secret rotation); the timestamp
must be within a tolerance so captured requests cannot be replayed later.
"""
import hashlib
import hmac
import logging

import httpx

from billing import ledger
from billing.packs import PACKS, Pack, pack_for_price, paddle_price_ids
from billing.settings import get_settings

logger = logging.getLogger('billing.paddle')
BASE = {'sandbox': 'https://sandbox-api.paddle.com', 'live': 'https://api.paddle.com'}
REFUND_ACTIONS = {'refund', 'chargeback'}


class PaddleError(Exception):
    pass


def http_client() -> httpx.Client:          # replaced in tests
    return httpx.Client(timeout=15)


def verify(header: str, raw: bytes, secret: str, now: float, tolerance: float) -> bool:
    if not header or not secret:
        return False
    parts = [p.split('=', 1) for p in header.split(';') if '=' in p]
    ts = next((v for k, v in parts if k == 'ts'), None)
    signatures = [v for k, v in parts if k == 'h1']
    try:
        stamp = int(ts)
    except (TypeError, ValueError):
        return False
    if not signatures or abs(now - stamp) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f'{stamp}:'.encode() + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in signatures)


def create_transaction(pack: Pack, account_id: str) -> str:
    settings = get_settings()
    price = paddle_price_ids().get(pack.id)
    if not settings.paddle_api_key or not price:
        raise PaddleError('not_configured')
    with http_client() as http:
        try:
            response = http.post(f"{BASE[settings.paddle_environment]}/transactions",
                                 headers={'Authorization': f'Bearer {settings.paddle_api_key}'},
                                 json={'items': [{'price_id': price, 'quantity': 1}],
                                       'custom_data': {'account_id': account_id, 'pack': pack.id}})
        except httpx.HTTPError as exc:
            raise PaddleError('unreachable') from exc
    if response.status_code != 201:
        logger.error('Paddle refused a transaction', extra={'status': response.status_code})
        raise PaddleError('refused')
    return response.json()['data']['id']


def handle(conn, event: dict) -> str:
    """Apply one verified event. Returns an outcome label; unusable events are acknowledged, not retried."""
    kind, data = event.get('event_type'), event.get('data') or {}
    if kind == 'transaction.completed':
        return _purchase(conn, data)
    if kind in ('adjustment.created', 'adjustment.updated'):
        return _adjustment(conn, data)
    return 'ignored:event_type'


def _purchase(conn, data: dict) -> str:
    account_id = (data.get('custom_data') or {}).get('account_id')
    if not isinstance(account_id, str) or not account_id:
        logger.error('Paid transaction without an account id', extra={'transaction': data.get('id')})
        return 'ignored:no_account'
    prices = [(item.get('price') or {}).get('id') for item in data.get('items') or []]
    pack = next((p for p in map(pack_for_price, prices) if p), None)
    if pack is None:
        logger.error('Paid transaction for an unknown price', extra={'transaction': data.get('id')})
        return 'ignored:unknown_price'
    transaction = data['id']
    if conn.execute("SELECT 1 FROM billing.payments WHERE provider = 'paddle' AND provider_ref = %s", (transaction,)).fetchone():
        return 'duplicate'
    gross = int(str(((data.get('details') or {}).get('totals') or {}).get('grand_total') or 0))
    ledger.record_topup(conn, 'paddle', transaction, account_id, gross, str(data.get('currency_code') or 'USD'), pack.credits_micros)
    if ledger.is_closed(conn, account_id):
        logger.warning('Payment received for a closed account; refund it in Paddle', extra={'transaction': transaction})
    return 'credited'


def _adjustment(conn, data: dict) -> str:
    if data.get('action') not in REFUND_ACTIONS:
        return 'ignored:action'
    if data.get('status') != 'approved':
        return 'ignored:not_approved'
    payment = conn.execute("SELECT gross_minor, credits_micros FROM billing.payments WHERE provider = 'paddle' AND provider_ref = %s",
                           (data.get('transaction_id'),)).fetchone()
    if payment is None:
        return 'ignored:unknown_transaction'
    ref = f"paddle:{data['transaction_id']}:{data['id']}"
    if conn.execute("SELECT 1 FROM billing.ledger WHERE kind = 'refund' AND ref = %s", (ref,)).fetchone():
        return 'duplicate'
    total = int(str((data.get('totals') or {}).get('total') or 0))
    gross = payment['gross_minor']
    micros = payment['credits_micros'] if gross <= 0 else min(payment['credits_micros'], payment['credits_micros'] * total // gross)
    ledger.refund(conn, 'paddle', data['transaction_id'], micros, refund_ref=ref)
    return 'refunded'


def packs_on_sale() -> list[dict]:
    prices = paddle_price_ids()
    return [dict(id=p.id, usd_cents=p.usd_cents, credits=p.credits_micros // 1000, available=p.id in prices) for p in PACKS.values()]
