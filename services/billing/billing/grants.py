"""Free starter allowance: once per account, capped per day, open models only, expires after 30 days."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from billing import emails, ledger
from billing.settings import get_settings

STARTER_MICROS = 500_000          # 500 credits = $0.50
STARTER_DAYS = 30


@dataclass(frozen=True)
class GrantResult:
    granted: bool
    reason: Literal['granted', 'already_granted', 'daily_cap', 'email_unverified', 'email_in_use', 'disposable_email', 'account_closed']


class _Refused(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def grant_starter(conn, account_id: str, today: date, cap: int | None = None,
                  email: str | None = None, email_verified: bool = False) -> GrantResult:
    """Grant the free allowance once per account and once per mailbox.

    A refused attempt changes nothing: the daily cap is not used up and the mailbox is not
    marked as claimed, so the learner can try again after fixing the problem (the checks and
    writes run in a savepoint that is rolled back on refusal).
    """
    settings = get_settings()
    cap = settings.starter_grants_per_day if cap is None else cap
    ledger.ensure_account(conn, account_id)
    available, reserved, starter = ledger._lock(conn, account_id)
    ref = f'starter:{account_id}'
    if conn.execute("SELECT 1 FROM billing.ledger WHERE kind = 'grant' AND ref = %s", (ref,)).fetchone():
        return GrantResult(False, 'already_granted')
    if ledger.is_closed(conn, account_id):
        return GrantResult(False, 'account_closed')
    key = None
    if settings.require_verified_email:
        if not email_verified or not email or not emails.is_valid(email):
            return GrantResult(False, 'email_unverified')
        if emails.is_disposable(email):
            return GrantResult(False, 'disposable_email')
        key = emails.email_key(email)
    try:
        with conn.transaction():
            conn.execute('INSERT INTO billing.grant_days (day, count) VALUES (%s, 0) ON CONFLICT DO NOTHING', (today,))
            if conn.execute('UPDATE billing.grant_days SET count = count + 1 WHERE day = %s AND count < %s RETURNING count',
                            (today, cap)).fetchone() is None:
                raise _Refused('daily_cap')
            if key is not None and conn.execute('INSERT INTO billing.grant_emails (email_key, account_id) VALUES (%s, %s) '
                                                'ON CONFLICT DO NOTHING RETURNING email_key', (key, account_id)).fetchone() is None:
                raise _Refused('email_in_use')
    except _Refused as refused:
        return GrantResult(False, refused.reason)
    expires = datetime.combine(today + timedelta(days=STARTER_DAYS), time.min, tzinfo=timezone.utc)
    ledger._append(conn, account_id, STARTER_MICROS, 'grant', ref, expires_at=expires)
    ledger._save(conn, account_id, available + STARTER_MICROS, reserved, starter + STARTER_MICROS)
    return GrantResult(True, 'granted')


def expire_starter(conn, now: datetime) -> int:
    """Remove unspent starter credits whose grant has expired. Returns the number of accounts changed.

    Accounts with an open hold are skipped until the hold closes (holds last at most 15 minutes):
    otherwise the hold's starter portion would come back as ordinary spendable credit.
    """
    due = conn.execute("SELECT DISTINCT account_id FROM billing.ledger l WHERE kind = 'grant' AND expires_at <= %s "
                       "AND NOT EXISTS (SELECT 1 FROM billing.ledger e WHERE e.kind = 'adjust' AND e.ref = 'starter-expiry:' || l.account_id)",
                       (now,)).fetchall()
    changed = 0
    for row in due:
        account_id = row['account_id']
        available, reserved, starter = ledger._lock(conn, account_id)
        if reserved > 0:
            continue
        ledger._append(conn, account_id, -starter, 'adjust', f'starter-expiry:{account_id}')
        ledger._save(conn, account_id, available - starter, reserved, 0)
        changed += 1
    return changed
