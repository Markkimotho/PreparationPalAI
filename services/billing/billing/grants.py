"""Free starter allowance: once per account, capped per day, open models only, expires after 30 days."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from billing import ledger
from billing.settings import get_settings

STARTER_MICROS = 500_000          # 500 credits = $0.50
STARTER_DAYS = 30


@dataclass(frozen=True)
class GrantResult:
    granted: bool
    reason: Literal['granted', 'already_granted', 'daily_cap']


def grant_starter(conn, account_id: str, today: date, cap: int | None = None) -> GrantResult:
    cap = get_settings().starter_grants_per_day if cap is None else cap
    ledger.ensure_account(conn, account_id)
    available, reserved, starter = ledger._lock(conn, account_id)
    ref = f'starter:{account_id}'
    if conn.execute("SELECT 1 FROM billing.ledger WHERE kind = 'grant' AND ref = %s", (ref,)).fetchone():
        return GrantResult(False, 'already_granted')
    conn.execute('INSERT INTO billing.grant_days (day, count) VALUES (%s, 0) ON CONFLICT DO NOTHING', (today,))
    taken = conn.execute('UPDATE billing.grant_days SET count = count + 1 WHERE day = %s AND count < %s RETURNING count',
                         (today, cap)).fetchone()
    if taken is None:
        return GrantResult(False, 'daily_cap')
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
