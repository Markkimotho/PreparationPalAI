"""RevenueCat: Apple and Google in-app purchases, validated by RevenueCat, applied to the ledger.

Authentication (revenuecat.com/docs/integrations/webhooks): every notification carries the Authorization
value configured in the RevenueCat dashboard; when signing is enabled it also carries
`X-RevenueCat-Webhook-Signature: t=<unix>,v1=<hmac>` over `<t>.<raw body>`. One-time purchases arrive as
`NON_RENEWING_PURCHASE`, refunds as `CANCELLATION`; retries reuse the event `id`.
"""
import hashlib
import hmac
import logging
import os
import re

from billing import ledger
from billing.packs import pack_for_product

logger = logging.getLogger('billing.revenuecat')
ACCOUNT = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def authorised(header: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest((header or '').encode(), expected.encode())


def signature_ok(header: str, raw: bytes, secret: str, now: float, tolerance: float) -> bool:
    parts = dict(p.split('=', 1) for p in (header or '').split(',') if '=' in p)
    try:
        stamp = int(parts.get('t', ''))
    except ValueError:
        return False
    if 'v1' not in parts or abs(now - stamp) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f'{stamp}.'.encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts['v1'])


def _account(event: dict) -> str | None:
    """The learner's account: app_user_id, else an alias, else the original id. Anonymous ids never count."""
    for candidate in [event.get('app_user_id'), *(event.get('aliases') or []), event.get('original_app_user_id')]:
        if isinstance(candidate, str) and ACCOUNT.fullmatch(candidate):
            return candidate
    return None


def _sandbox_allowed(account: str | None) -> bool:
    if os.environ.get('REVENUECAT_ACCEPT_SANDBOX', '').lower() == 'true':
        return True
    allowed = {a.strip() for a in os.environ.get('REVENUECAT_SANDBOX_ACCOUNTS', '').split(',') if a.strip()}
    return account in allowed


def handle(conn, payload: dict) -> str:
    event = payload.get('event') or {}
    kind = event.get('type')
    if kind not in ('NON_RENEWING_PURCHASE', 'CANCELLATION'):
        return 'ignored:event_type'
    account = _account(event)
    if event.get('environment') == 'SANDBOX' and not _sandbox_allowed(account):
        return 'ignored:sandbox'          # TestFlight testers pay nothing; only the review account is credited
    transaction = str(event.get('transaction_id') or '')
    if kind == 'NON_RENEWING_PURCHASE':
        if account is None:
            logger.error('Store purchase without a usable account id', extra={'event': event.get('id')})
            return 'ignored:no_account'
        pack = pack_for_product(str(event.get('product_id') or ''))
        if pack is None:
            logger.error('Store purchase for an unknown product', extra={'event': event.get('id')})
            return 'ignored:unknown_product'
        if conn.execute("SELECT 1 FROM billing.payments WHERE provider = 'revenuecat' AND provider_ref = %s", (transaction,)).fetchone():
            return 'duplicate'
        price = event.get('price')
        gross = round(float(price) * 100) if isinstance(price, (int, float)) and price > 0 else 0
        ledger.record_topup(conn, 'revenuecat', transaction, account, gross, 'USD', pack.credits_micros)
        return 'credited'
    payment = conn.execute("SELECT credits_micros FROM billing.payments WHERE provider = 'revenuecat' AND provider_ref = %s",
                           (transaction,)).fetchone()
    if payment is None:
        return 'ignored:unknown_transaction'
    ref = f"revenuecat:{transaction}:{event.get('id')}"
    if conn.execute("SELECT 1 FROM billing.ledger WHERE kind = 'refund' AND ref = %s", (ref,)).fetchone():
        return 'duplicate'
    if conn.execute("SELECT 1 FROM billing.ledger WHERE kind = 'refund' AND ref LIKE %s", (f'revenuecat:{transaction}:%',)).fetchone():
        return 'duplicate'                # a store refund is always whole: never apply a second one
    ledger.refund(conn, 'revenuecat', transaction, payment['credits_micros'], refund_ref=ref)
    return 'refunded'
