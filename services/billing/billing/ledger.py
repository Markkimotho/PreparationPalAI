"""The credit ledger. Every function takes an open transaction (`db.transaction()`).

Rules that keep money correct:
  * Each operation first locks the account's balance row (FOR UPDATE), so operations on one
    account are serialised and balances can never be overdrawn by concurrent requests.
  * The ledger is append-only and every entry is idempotent on (kind, ref).
  * Invariant: available + reserved == SUM(ledger.amount) and reserved == the open holds.
"""
from dataclasses import dataclass
from datetime import datetime


class InsufficientCredits(Exception):
    def __init__(self, balance_micros: int, required_micros: int, premium_requires_purchase: bool = False):
        super().__init__('Not enough credits')
        self.balance_micros = balance_micros
        self.required_micros = required_micros
        self.premium_requires_purchase = premium_requires_purchase


class AccountClosed(Exception):
    """The learner deleted their account; no new work may be reserved."""


@dataclass(frozen=True)
class Balance:
    available_micros: int
    reserved_micros: int
    starter_micros: int


@dataclass(frozen=True)
class SettleResult:
    charged_micros: int
    written_off_micros: int
    balance_micros: int


@dataclass(frozen=True)
class LedgerRow:
    id: int
    amount_micros: int
    hold_micros: int
    kind: str
    ref: str
    price_version: int | None
    created_at: datetime


def ensure_account(conn, account_id: str) -> None:
    conn.execute('INSERT INTO billing.accounts (id) VALUES (%s) ON CONFLICT DO NOTHING', (account_id,))
    conn.execute('INSERT INTO billing.balances (account_id) VALUES (%s) ON CONFLICT DO NOTHING', (account_id,))


def _lock(conn, account_id: str) -> tuple[int, int, int]:
    row = conn.execute('SELECT available_micros, reserved_micros, starter_micros FROM billing.balances '
                       'WHERE account_id = %s FOR UPDATE', (account_id,)).fetchone()
    if row is None:
        raise KeyError(account_id)
    return row['available_micros'], row['reserved_micros'], row['starter_micros']


def _save(conn, account_id: str, available: int, reserved: int, starter: int) -> None:
    assert available >= 0 and reserved >= 0 and 0 <= starter <= available, (available, reserved, starter)
    conn.execute('UPDATE billing.balances SET available_micros=%s, reserved_micros=%s, starter_micros=%s WHERE account_id=%s',
                 (available, reserved, starter, account_id))


def _append(conn, account_id: str, amount: int, kind: str, ref: str, hold: int = 0,
            price_version: int | None = None, expires_at=None) -> bool:
    """Insert a ledger row. False means this (kind, ref) already exists: the operation is a replay."""
    row = conn.execute('INSERT INTO billing.ledger (account_id, amount_micros, hold_micros, kind, ref, price_version, expires_at) '
                       'VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (kind, ref) DO NOTHING RETURNING id',
                       (account_id, amount, hold, kind, ref, price_version, expires_at)).fetchone()
    return row is not None


def _tier(conn, alias: str) -> str:
    row = conn.execute('SELECT tier FROM billing.prices WHERE alias = %s ORDER BY version DESC LIMIT 1', (alias,)).fetchone()
    return row['tier'] if row else 'open'


def balance(conn, account_id: str) -> Balance:
    row = conn.execute('SELECT available_micros, reserved_micros, starter_micros FROM billing.balances WHERE account_id = %s',
                       (account_id,)).fetchone()
    return Balance(0, 0, 0) if row is None else Balance(row['available_micros'], row['reserved_micros'], row['starter_micros'])


def credit(conn, account_id: str, micros: int, kind: str, ref: str, expires_at=None) -> int:
    """Add funds. Returns the available balance. A replayed (kind, ref) changes nothing."""
    if kind not in ('grant', 'topup', 'adjust') or micros <= 0:
        raise ValueError('credit needs a positive amount and kind grant, topup or adjust')
    ensure_account(conn, account_id)
    available, reserved, starter = _lock(conn, account_id)
    if not _append(conn, account_id, micros, kind, ref, expires_at=expires_at):
        return available
    _save(conn, account_id, available + micros, reserved, starter)
    return available + micros


def record_topup(conn, provider: str, provider_ref: str, account_id: str, gross_minor: int,
                 currency: str, credits_micros: int) -> int:
    """Record a payment and credit it exactly once, however often the provider repeats the webhook."""
    ensure_account(conn, account_id)
    inserted = conn.execute(
        'INSERT INTO billing.payments (provider, provider_ref, account_id, gross_minor, currency, credits_micros, status) '
        "VALUES (%s, %s, %s, %s, %s, %s, 'completed') ON CONFLICT (provider, provider_ref) DO NOTHING RETURNING id",
        (provider, provider_ref, account_id, gross_minor, currency, credits_micros)).fetchone()
    if inserted is None:
        return balance(conn, account_id).available_micros
    return credit(conn, account_id, credits_micros, 'topup', f'{provider}:{provider_ref}')


def reserve(conn, account_id: str, request_id: str, micros: int, action: str, alias: str) -> int:
    """Hold funds for one action. Premium aliases may only use purchased (non-starter) credits."""
    if micros < 0:
        raise ValueError('reservation cannot be negative')
    ensure_account(conn, account_id)
    available, reserved, starter = _lock(conn, account_id)
    if is_closed(conn, account_id):
        raise AccountClosed(account_id)
    existing = conn.execute('SELECT account_id FROM billing.reservations WHERE request_id = %s', (request_id,)).fetchone()
    if existing is not None:
        if existing['account_id'] != account_id:
            raise ValueError('request id already belongs to another account')
        return available
    tier = _tier(conn, alias)
    usable = available - starter if tier == 'premium' else available
    if usable < micros:
        raise InsufficientCredits(available, micros, premium_requires_purchase=(tier == 'premium' and available >= micros))
    starter_hold = 0 if tier == 'premium' else min(starter, micros)
    conn.execute('INSERT INTO billing.reservations (request_id, account_id, amount_micros, action, alias, starter_hold_micros, tier) '
                 'VALUES (%s, %s, %s, %s, %s, %s, %s)', (request_id, account_id, micros, action, alias, starter_hold, tier))
    _append(conn, account_id, 0, 'reserve', request_id, hold=micros)
    _save(conn, account_id, available - micros, reserved + micros, starter - starter_hold)
    return available - micros


def _reservation_account(conn, request_id: str) -> str | None:
    row = conn.execute('SELECT account_id FROM billing.reservations WHERE request_id = %s', (request_id,)).fetchone()
    return row['account_id'] if row else None


def settle(conn, request_id: str, charges_micros: int, price_version: int) -> SettleResult:
    """Charge the real cost of an action and return whatever the hold did not use.

    A cost above the hold is taken from available funds; anything the balance cannot cover is
    written off (reported, never negative). A settle that arrives after the sweeper released
    the hold still charges, so a slow stream is never free.
    """
    if charges_micros < 0:
        raise ValueError('charge cannot be negative')
    account_id = _reservation_account(conn, request_id)
    if account_id is None:
        raise KeyError(request_id)
    available, reserved, starter = _lock(conn, account_id)
    res = conn.execute('SELECT * FROM billing.reservations WHERE request_id = %s FOR UPDATE', (request_id,)).fetchone()
    if res['status'] == 'settled':
        return SettleResult(res['charged_micros'] or 0, 0, available)
    holding = res['status'] == 'open'
    hold = res['amount_micros'] if holding else 0
    starter_hold = res['starter_hold_micros'] if holding else 0
    premium = res['tier'] == 'premium'
    if charges_micros <= hold:
        charged, written_off = charges_micros, 0
        available += hold - charges_micros
        starter += starter_hold - min(starter_hold, charges_micros)
    else:
        extra = charges_micros - hold
        take = min(extra, available - starter if premium else available)
        charged, written_off = hold + take, extra - take
        available -= take
        if not premium:
            starter = max(0, starter - take)
    reserved -= hold
    _append(conn, account_id, -charged, 'settle', request_id, hold=-hold, price_version=price_version)
    _save(conn, account_id, available, reserved, starter)
    conn.execute("UPDATE billing.reservations SET status = 'settled', charged_micros = %s WHERE request_id = %s", (charged, request_id))
    return SettleResult(charged, written_off, available)


def release(conn, request_id: str) -> None:
    """Return an unused hold. Safe to repeat; ignores unknown or already-closed reservations."""
    account_id = _reservation_account(conn, request_id)
    if account_id is None:
        return
    available, reserved, starter = _lock(conn, account_id)
    res = conn.execute('SELECT * FROM billing.reservations WHERE request_id = %s FOR UPDATE', (request_id,)).fetchone()
    if res['status'] != 'open':
        return
    _append(conn, account_id, 0, 'release', request_id, hold=-res['amount_micros'])
    _save(conn, account_id, available + res['amount_micros'], reserved - res['amount_micros'], starter + res['starter_hold_micros'])
    conn.execute("UPDATE billing.reservations SET status = 'released' WHERE request_id = %s", (request_id,))


def is_closed(conn, account_id: str) -> bool:
    row = conn.execute('SELECT closed_at FROM billing.accounts WHERE id = %s', (account_id,)).fetchone()
    return bool(row and row['closed_at'])


def close_account(conn, account_id: str) -> None:
    """Stop an account taking new work. Open holds are released first; the ledger is kept. Idempotent."""
    ensure_account(conn, account_id)        # an account that never transacted still gets a closed tombstone
    _lock(conn, account_id)
    for row in conn.execute("SELECT request_id FROM billing.reservations WHERE account_id = %s AND status = 'open'", (account_id,)).fetchall():
        release(conn, row['request_id'])
    conn.execute('UPDATE billing.accounts SET closed_at = COALESCE(closed_at, now()) WHERE id = %s', (account_id,))


def refund(conn, provider: str, provider_ref: str, micros: int, refund_ref: str | None = None) -> SettleResult:
    """Claw back purchased credits for a refunded payment, never below zero and never starter credits.

    `refund_ref` identifies one refund (for example one Paddle adjustment) so a payment can be refunded
    partially more than once; each ref is applied exactly once.
    """
    payment = conn.execute('SELECT account_id FROM billing.payments WHERE provider = %s AND provider_ref = %s',
                           (provider, provider_ref)).fetchone()
    if payment is None:
        raise KeyError(f'{provider}:{provider_ref}')
    account_id, ref = payment['account_id'], refund_ref or f'{provider}:{provider_ref}'
    available, reserved, starter = _lock(conn, account_id)
    prior = conn.execute("SELECT amount_micros FROM billing.ledger WHERE kind = 'refund' AND ref = %s", (ref,)).fetchone()
    if prior is not None:
        return SettleResult(-prior['amount_micros'], 0, available)
    take = min(micros, available - starter)
    _append(conn, account_id, -take, 'refund', ref)
    _save(conn, account_id, available - take, reserved, starter)
    status = 'refunded' if take == micros else 'refunded_partially'
    conn.execute('UPDATE billing.payments SET status = %s WHERE provider = %s AND provider_ref = %s', (status, provider, provider_ref))
    return SettleResult(take, micros - take, available - take)


def adjust(conn, account_id: str, delta_micros: int, ref: str) -> SettleResult:
    """Signed correction (for example reconciliation of unbilled usage). A charge cannot go below zero."""
    ensure_account(conn, account_id)
    available, reserved, starter = _lock(conn, account_id)
    prior = conn.execute("SELECT amount_micros FROM billing.ledger WHERE kind = 'adjust' AND ref = %s", (ref,)).fetchone()
    if prior is not None:
        return SettleResult(max(0, -prior['amount_micros']), 0, available)
    if delta_micros >= 0:
        _append(conn, account_id, delta_micros, 'adjust', ref)
        _save(conn, account_id, available + delta_micros, reserved, starter)
        return SettleResult(0, 0, available + delta_micros)
    take = min(-delta_micros, available)
    _append(conn, account_id, -take, 'adjust', ref)
    _save(conn, account_id, available - take, reserved, max(0, starter - take))
    return SettleResult(take, -delta_micros - take, available - take)


def history(conn, account_id: str, limit: int = 50, before_id: int | None = None) -> list[LedgerRow]:
    rows = conn.execute('SELECT id, amount_micros, hold_micros, kind, ref, price_version, created_at FROM billing.ledger '
                        'WHERE account_id = %s AND (%s::bigint IS NULL OR id < %s) ORDER BY id DESC LIMIT %s',
                        (account_id, before_id, before_id, limit)).fetchall()
    return [LedgerRow(**r) for r in rows]


def invariant_holds(conn, account_id: str) -> bool:
    b = balance(conn, account_id)
    total = conn.execute('SELECT COALESCE(SUM(amount_micros), 0) AS t FROM billing.ledger WHERE account_id = %s', (account_id,)).fetchone()['t']
    holds = conn.execute("SELECT COALESCE(SUM(amount_micros), 0) AS t FROM billing.reservations WHERE account_id = %s AND status = 'open'",
                         (account_id,)).fetchone()['t']
    return (b.available_micros >= 0 and b.reserved_micros >= 0 and b.starter_micros <= b.available_micros
            and b.available_micros + b.reserved_micros == total and b.reserved_micros == holds)
