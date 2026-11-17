# billing

Owns every credit balance for PreparationPalAI. Nothing else writes balances.

- **Money** is integer micro-dollars (1 credit = 1,000 micros). No floats.
- **Ledger** is append-only (a trigger rejects UPDATE and DELETE). `amount_micros` changes
  total funds (available + reserved); reserve and release rows move money between the two and
  carry their size in `hold_micros`. Invariant per account:
  `available + reserved == SUM(ledger.amount_micros)`.
- **Idempotency**: `UNIQUE(kind, ref)` on the ledger and `UNIQUE(provider, provider_ref)` on payments.

## Develop

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
docker compose -f docker-compose.test.yml up -d     # throwaway Postgres on 127.0.0.1:15432
.venv/bin/pytest -q
docker compose -f docker-compose.test.yml down -v
```

Design: `specs/2026-11-17-hosted-product-design.md` section 7.3. Plan: `specs/plans/2026-11-17-plan-2-billing-service.md`.
