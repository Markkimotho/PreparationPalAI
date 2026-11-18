"""Scheduled safety nets: free stale holds, expire starter credits, reconcile against the gateway.

    python -m billing.jobs sweep                  every 5 minutes
    python -m billing.jobs expire                 hourly
    python -m billing.jobs reconcile [--date D]   nightly, for the previous UTC day
    python -m billing.jobs check-prices           nightly

`reconcile` and `check-prices` exit 3 when they find a problem, so cron or a monitor can alert.
"""
import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from psycopg.types.json import Jsonb

from billing import db, grants, ledger
from billing.pricing import Usage, charge_micros, current_prices
from billing.settings import get_settings

STALE_MINUTES = 15
PRICE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ReconcileReport:
    matched: int
    missing_in_ledger: int
    drift_micros: int


@dataclass(frozen=True)
class PriceDiff:
    alias: str
    ours_input: float
    gateway_input: float
    ours_output: float
    gateway_output: float


def sweep(conn, now: datetime, limit: int = 500) -> int:
    """Release holds older than STALE_MINUTES. A late settle for a swept hold still charges."""
    stale = conn.execute("SELECT request_id FROM billing.reservations WHERE status = 'open' AND created_at < %s "
                         "ORDER BY created_at LIMIT %s", (now - timedelta(minutes=STALE_MINUTES), limit)).fetchall()
    for row in stale:
        ledger.release(conn, row['request_id'])
    return len(stale)


def reconcile(conn, spend_rows: list[dict], key_alias: str) -> ReconcileReport:
    """Compare what the gateway says was used with what the ledger charged, and charge the difference.

    Only successful calls from this app's key that carry a reservation id are considered. The
    correction is idempotent (one `adjust` per reservation) and never takes a balance below zero.
    """
    prices = current_prices(conn)
    per_reservation: dict[str, dict] = {}
    for r in spend_rows:
        meta = r.get('metadata') or {}
        correlation = meta.get('spend_logs_metadata') or {}
        reservation_id = correlation.get('request_id')
        if (meta.get('user_api_key_alias') != key_alias or r.get('status') != 'success'
                or not reservation_id or correlation.get('action') == 'unscoped'):
            continue
        entry = per_reservation.setdefault(reservation_id, dict(account=r.get('end_user') or '', usage={}))
        totals = entry['usage'].setdefault(r['model_group'], [0, 0])
        totals[0] += int(r.get('prompt_tokens') or 0)
        totals[1] += int(r.get('completion_tokens') or 0)
    matched = missing = drift = 0
    for reservation_id, entry in per_reservation.items():
        expected = sum(charge_micros(Usage(alias, i, o), prices[alias]) for alias, (i, o) in entry['usage'].items() if alias in prices)
        found = conn.execute('SELECT account_id, status, charged_micros FROM billing.reservations WHERE request_id = %s', (reservation_id,)).fetchone()
        settled = found is not None and found['status'] == 'settled'
        corrected = int(conn.execute("SELECT COALESCE(-SUM(amount_micros), 0) AS n FROM billing.ledger WHERE kind = 'adjust' AND ref = %s",
                                     (f'reconcile:{reservation_id}',)).fetchone()['n'])         # SUM(bigint) is numeric in Postgres
        actual = (found['charged_micros'] or 0) if settled else 0
        shortfall = expected - actual - corrected
        if shortfall <= 0:
            matched += 1
            continue
        drift += shortfall
        missing += 0 if settled else 1
        account = found['account_id'] if found else entry['account']
        if account:
            ledger.adjust(conn, account, -(expected - actual), f'reconcile:{reservation_id}')
    return ReconcileReport(matched, missing, drift)


def check_prices(conn, model_info: list[dict]) -> list[PriceDiff]:
    """Aliases whose gateway price differs from ours. Never changes prices: repricing is a decision."""
    ours = current_prices(conn)
    diffs = []
    for entry in model_info:
        alias, info = entry.get('model_name'), entry.get('model_info') or {}
        if alias not in ours or info.get('input_cost_per_token') is None or info.get('output_cost_per_token') is None:
            continue
        gi, go = round(info['input_cost_per_token'] * 1e6, 6), round(info['output_cost_per_token'] * 1e6, 6)
        oi, oo = round(float(ours[alias].input_per_m), 6), round(float(ours[alias].output_per_m), 6)
        if abs(gi - oi) > PRICE_TOLERANCE or abs(go - oo) > PRICE_TOLERANCE:
            diffs.append(PriceDiff(alias, oi, gi, oo, go))
    return diffs


def fetch_spend_rows(client: httpx.Client, admin_key: str, day: date, page_size: int = 200) -> list[dict]:
    rows, page = [], 1
    while True:
        response = client.get('/spend/logs/v2', headers={'Authorization': f'Bearer {admin_key}'}, params={
            'start_date': f'{day} 00:00:00', 'end_date': f'{day + timedelta(days=1)} 00:00:00',
            'page': page, 'page_size': page_size})
        response.raise_for_status()
        batch = response.json()['data']
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        page += 1


def fetch_model_info(client: httpx.Client, admin_key: str) -> list[dict]:
    response = client.get('/model/info', headers={'Authorization': f'Bearer {admin_key}'})
    response.raise_for_status()
    return response.json()['data']


def record_run(conn, name: str, result: dict, problem: bool) -> None:
    conn.execute('INSERT INTO billing.job_runs (name, problem, result) VALUES (%s, %s, %s)', (name, problem, Jsonb(result)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='billing.jobs')
    parser.add_argument('command', choices=['sweep', 'expire', 'reconcile', 'check-prices'])
    parser.add_argument('--date', help='UTC day to reconcile, YYYY-MM-DD (default: yesterday)')
    args = parser.parse_args(argv)
    settings = get_settings()
    if not settings.database_url:
        sys.exit('Set BILLING_DATABASE_URL')
    db.configure(settings.database_url)
    try:
        now = datetime.now(timezone.utc)
        if args.command == 'sweep':
            with db.transaction() as conn:
                result = {'released': sweep(conn, now)}
        elif args.command == 'expire':
            with db.transaction() as conn:
                result = {'accounts_expired': grants.expire_starter(conn, now)}
        else:
            if not settings.gateway_admin_key:
                sys.exit('Set GATEWAY_ADMIN_KEY')
            with httpx.Client(base_url=settings.gateway_base_url, timeout=30) as gateway:
                if args.command == 'reconcile':
                    day = date.fromisoformat(args.date) if args.date else (now - timedelta(days=1)).date()
                    rows = fetch_spend_rows(gateway, settings.gateway_admin_key, day)
                    with db.transaction() as conn:
                        report = reconcile(conn, rows, settings.gateway_key_alias)
                    result = dict(asdict(report), day=str(day), gateway_rows=len(rows))
                else:
                    with db.transaction() as conn:
                        diffs = check_prices(conn, fetch_model_info(gateway, settings.gateway_admin_key))
                    result = {'price_diffs': [asdict(d) for d in diffs]}
        print(json.dumps(result))
        problem = bool(result.get('drift_micros') or result.get('missing_in_ledger') or result.get('price_diffs'))
        with db.transaction() as conn:
            record_run(conn, args.command, result, problem)
        return 3 if problem else 0
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
