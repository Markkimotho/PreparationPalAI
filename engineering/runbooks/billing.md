---
description: Operate the credit ledger, prices, starter credits, scheduled safety nets, and billing alerts.
---
# Billing and credits

Hosted deployments charge learners per use from a prepaid credit balance. The
`services/billing` service owns every balance. The app never does money arithmetic: it
asks billing to reserve credits before a model action, then reports the real token usage so
billing can price and charge it.

## How one action is charged

1. `BillingMiddleware` (`app/metered.py`) recognises a model-backed route from its route table.
2. It asks billing to **reserve** credits. Billing prices the worst case from token ceilings
   (`BILLING_RESERVE_INPUT_TOKENS`, `BILLING_RESERVE_OUTPUT_TOKENS`, calls per action). Not enough
   credits returns HTTP 402 with the balance, the amount needed, and a top-up link. The route never runs.
3. The route runs. Every model call records its tokens in the request's usage meter.
4. After the response ends, or the client disconnects, the middleware **settles**: billing prices
   the real usage and charges it. Unused hold returns to the balance. If nothing ran, the hold is released.

One credit is $0.001. Open models cost 1.5 times provider cost, premium models 1.25 times.
Prices live in `billing.prices` (seeded from `billing/prices.seed.yaml`) and are versioned; every
charge records the version it used.

## Rules the ledger enforces

- Money is integer micro-dollars. The ledger is append-only (a database trigger rejects edits).
- A balance never goes below zero. Usage the balance cannot cover is **written off** and counted
  in `billing_written_off_micros_total`.
- Parallel requests cannot overdraw: each operation locks the account's balance row first.
- Every ledger entry and payment is idempotent, so repeated webhooks or retries credit or charge once.
- A settle that arrives after the sweeper released its hold still charges the real usage.
- **Starter credits** (500 credits, 30 days, open models only) are spent first and never pay for
  premium models. A daily cap (`STARTER_GRANTS_PER_DAY`, default 200) bounds free spend.
- Refunds claw back purchased credits only, never below zero.

## If billing is down

- Before the action: the app returns 503 "Billing is temporarily unavailable" and runs nothing.
- After the action: usage is queued in `data/usage/billing_outbox.sqlite3` and settled when billing
  returns (flushed at the start of each metered request, or run `python -m app.billing_outbox`).
  Keep the `usage_data` volume mounted on both web and worker.

## Scheduled safety nets

The `billing-jobs` container runs `python -m billing.scheduler`.

| Job | When | What it does |
| --- | --- | --- |
| `sweep` | every 5 minutes | Releases holds older than 15 minutes. |
| `expire` | hourly | Removes unspent starter credits older than 30 days (skips accounts with an open hold). |
| `reconcile` | 02:00 UTC | Compares the gateway's spend logs for the previous day with the ledger and charges anything missed, once. |
| `check-prices` | 02:10 UTC | Reports gateway model prices that differ from `billing.prices`. It never reprices. |

Run one by hand: `docker compose -f docker-compose.hosted.yml run --rm billing-jobs python -m billing.jobs reconcile --date 2026-11-16`.
Exit code 3 means it found a problem. Results are stored in `billing.job_runs` and exported by the API's `/metrics`.

## Publish new prices

```python
from billing import db, pricing
with db.transaction() as conn:
    pricing.publish_prices(conn, [dict(alias='open-default', tier='open', input_per_m='0.80', output_per_m='3.50', multiplier='1.5')])
```

Aliases you do not mention carry over. A multiplier below 1 is rejected. New prices apply to new
charges only; old ledger rows keep their `price_version`.

## Alerts

| Alert | Meaning and first step |
| --- | --- |
| `BillingUnavailable` | The service is down and model actions fail closed. Check `docker compose logs billing billing-db`. |
| `BillingWriteOffs` | More than $1 a day of usage could not be charged. Raise the reservation sizing or look for one account overspending. |
| `BillingHoldsStuck` | Many open holds. Check that `billing-jobs` is running. |
| `BillingReconcileDrift` | The gateway recorded usage the ledger missed. The reconciler already charged it; find why settle failed (usually an outage, see the outbox). |
| `BillingPriceDrift` | A provider price changed. Publish new prices before margins erode. |
| `BillingJobsStale` | The nightly reconcile has not run for over a day. |
| `BillingMarginNegative` | Charges are below provider cost. Check the multiplier and prices. |

## Develop and test

```bash
cd services/billing
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
docker compose -f docker-compose.test.yml up -d
.venv/bin/pytest -q
```

After changing the API, regenerate the contract: `python -m billing.api --dump-openapi > ../../contracts/billing.yaml`.
