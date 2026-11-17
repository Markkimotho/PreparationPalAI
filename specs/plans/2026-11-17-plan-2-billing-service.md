# Plan 2: Billing service and metered model routes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone billing service that owns every credit balance (append-only ledger, versioned prices, reserve then settle, starter grant, sweeper, reconciler), and app wiring so every model-backed route is charged from the real usage recorded by Plan 1.

**Architecture:** `services/billing/` is its own FastAPI service with its own Postgres schema, tests, Dockerfile and README. The app talks to it only through `contracts/billing.yaml` via `app/billing_client.py`. A `metered(action)` wrapper reserves before a model route runs, feeds the Plan 1 meter, and settles in a `finally`. `BILLING_ENABLED=false` (default) makes all of it a no-op for self-hosting.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3 (pool), Postgres 16, plain SQL migrations, httpx, pytest, Prometheus client.

**Spec:** `specs/2026-11-17-hosted-product-design.md` (sections 7.3, 7.4, 8, 12, 13, 15)

## Global Constraints

- Money is integer micro-dollars (`*_micros`, `BIGINT`) everywhere; 1 credit = 1,000 micros. No floats in storage or arithmetic on balances.
- Ledger is append-only: no `UPDATE` or `DELETE` on `ledger`. Kinds: `grant | topup | reserve | settle | release | refund | adjust`.
- `balances` row changes only in the same transaction as its ledger row, under `SELECT ... FOR UPDATE`.
- Invariant: for every account, `available_micros + reserved_micros == SUM(ledger.amount_micros)` and `available_micros >= 0`.
- Charge formula: `ceil((in × input_per_m + out × output_per_m + cache_read × cache_read_per_m) × multiplier)` micros per record, summed per request. Multipliers: open `1.5`, premium `1.25`. Every settle records `price_version`.
- Starter grant: 500 credits (500,000 micros), open aliases only, expires 30 days after grant, once per account, global cap `STARTER_GRANTS_PER_DAY` (default 200).
- Reservations older than 15 minutes are released by the sweeper.
- Billing API is internal: bearer service token, never routed through Caddy.
- 402 body shape (exact): `{"detail": "Not enough credits for this action.", "balance_credits": int, "required_credits": int, "top_up_url": str}`.
- Account key until Plan 3 lands: the app's `workspace_id`.
- Commit messages carry no Claude co-author line.

## Review Focus

1. Two tabs fire the same action at once on a balance that covers one → exactly one runs; the other gets 402. Test in Task 3.
2. Client disconnects mid-stream (SSE generator closed) → settle still runs for usage already recorded; nothing stays reserved. Test in Task 6.
3. Agent loop keeps calling tools past its reservation → the call that crosses the line is charged, the next call is refused, the user sees a clear "credits ran out during this action" error, and the balance never goes negative. Test in Task 6.
4. Payment provider retries the same webhook or refunds after credits were spent → credited once; refund leaves balance at 0, not negative, and records the shortfall. Test in Task 3.
5. Starter credits used on a premium alias → 402 explaining premium needs purchased credits. Test in Task 4.

---

### Task 1: Service scaffold, schema and test database (DONE, 10 tests)

Design decision made here: ledger `amount_micros` changes TOTAL funds (grants and top-ups positive, settles negative). Reserve and release rows have `amount_micros = 0` and carry the hold in a new `hold_micros` column, so `available + reserved == SUM(ledger.amount_micros)` holds exactly and total spend is simply `-SUM(amount) WHERE kind='settle'`. `reservations` also gains `charged_micros`.

**Files:**
- Create: `services/billing/pyproject.toml`, `services/billing/billing/__init__.py`, `billing/settings.py`, `billing/db.py`, `billing/migrations/001_init.sql`, `billing/migrate.py`, `services/billing/Dockerfile`, `services/billing/README.md`, `services/billing/docker-compose.test.yml`, `services/billing/tests/conftest.py`, `tests/test_migrations.py`

**Interfaces:**
- Produces tables (schema `billing`): `accounts(id TEXT PK, created_at)`, `ledger(id BIGSERIAL, account_id, amount_micros BIGINT, kind TEXT CHECK(...), ref TEXT, price_version INT NULL, expires_at TIMESTAMPTZ NULL, created_at)` with `UNIQUE(kind, ref)`, `balances(account_id PK, available_micros BIGINT CHECK (>=0), reserved_micros BIGINT CHECK (>=0), starter_micros BIGINT CHECK (>=0 AND starter_micros <= available_micros))`, `reservations(request_id PK, account_id, amount_micros, action, alias, status CHECK IN ('open','settled','released'), created_at)`, `prices(version, alias, tier, input_per_m, output_per_m, cache_read_per_m, multiplier NUMERIC, effective_from, PK(version, alias))`, `payments(id, provider, provider_ref, account_id, gross_minor, currency, credits_micros, status, UNIQUE(provider, provider_ref))`, `grant_days(day DATE PK, count INT)`, `schema_migrations(version)`.
- Produces: `billing.db.transaction() -> ContextManager[psycopg.Connection]`; fixture `db` that applies migrations to `BILLING_TEST_DATABASE_URL` and truncates between tests.

- [ ] **Step 1: Tests**: `test_migrations_apply_twice_idempotently`; `test_ledger_rejects_update_and_delete` (a trigger raises on UPDATE/DELETE); `test_balance_cannot_go_negative` (CHECK).
- [ ] **Step 2: Run** `docker compose -f services/billing/docker-compose.test.yml up -d && pytest services/billing/tests -q` → FAIL.
- [ ] **Step 3: Implement** migration SQL and runner (applies `migrations/*.sql` in order inside a transaction, records version).
- [ ] **Step 4: Run** → PASS. **Step 5: Commit.**

### Task 2: Prices and charge arithmetic (DONE, 12 tests)

**Files:**
- Create: `billing/pricing.py`, `billing/prices.seed.yaml`, `tests/test_pricing.py`

**Interfaces:**
- Produces: `@dataclass Price(alias, tier, input_per_m: Decimal, output_per_m: Decimal, cache_read_per_m: Decimal, multiplier: Decimal, version: int)`; `@dataclass Usage(alias: str, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0)`; `def charge_micros(usage: Usage, price: Price) -> int`; `def current_prices(conn) -> dict[str, Price]`; `def publish_prices(conn, rows: list[dict]) -> int` (inserts a new version, returns it); `def ceiling_micros(price: Price, input_tokens: int, output_tokens: int) -> int`.

- [ ] **Step 1: Tests** (values from spec 8.2 via the seed file prices):
  - `test_glm_quiz_charge`: Usage(open-default, 8000, 2500) + guard Usage(guard, 12000, 80) → total within 1 credit of 13.9 credits (13,900 micros ± 100).
  - `test_rounds_up_never_zero`: Usage(guard, 1, 0) → 1.
  - `test_premium_uses_premium_multiplier`.
  - `test_publish_creates_new_version_and_old_charges_keep_theirs`.
  - `test_unknown_alias_raises` (`KeyError` subclass `UnknownAlias`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** with `Decimal` and `ROUND_CEILING`. **Step 4: Run** → PASS. **Step 5: Commit.**

### Task 3: Ledger operations (DONE, 19 tests incl. concurrency and a 300-step random invariant run)

Decisions made here: migration `002_hold_details.sql` adds `starter_hold_micros` and `tier` to reservations (done now instead of Task 4 because reserve, settle and release all need them); a settle that arrives after the sweeper released its hold still charges (late settle); `record_topup`, `adjust` and `balance` added; refunds never touch starter credits.

**Files:**
- Create: `billing/ledger.py`, `tests/test_ledger.py`, `tests/test_ledger_concurrency.py`

**Interfaces:**
- Produces (all take `conn`, all idempotent on their key, all raise `InsufficientCredits(balance_micros, required_micros)` where relevant):
  - `ensure_account(conn, account_id) -> None`
  - `credit(conn, account_id, micros, kind: Literal["grant","topup","adjust"], ref, expires_at=None) -> int` (balance after)
  - `reserve(conn, account_id, request_id, micros, action, alias) -> int`
  - `settle(conn, request_id, charges_micros: int, price_version: int) -> SettleResult(charged_micros, written_off_micros, balance_micros)`; charges actual even above the reservation, up to reserved + available; any remainder is `written_off_micros` (metric, no negative balance)
  - `release(conn, request_id) -> None`
  - `refund(conn, provider, provider_ref, micros) -> SettleResult` (clamped at zero, shortfall reported)
  - `balance(conn, account_id) -> Balance(available_micros, reserved_micros, starter_micros)`
  - `history(conn, account_id, limit=50, before_id=None) -> list[LedgerRow]`

- [ ] **Step 1: Tests**:
  - `test_reserve_settle_release_math`: 10,000 available, reserve 3,000, settle 1,200 → available 8,800, reserved 0, ledger sums to 8,800.
  - `test_settle_above_reservation_charges_actual`: reserve 1,000, settle 1,500 with 9,000 available → available 8,500.
  - `test_settle_beyond_balance_writes_off`: available 0 after reserve 1,000, settle 1,500 → charged 1,000, written_off 500, available 0.
  - `test_reserve_same_request_id_twice_is_single_hold`.
  - `test_settle_twice_is_noop`, `test_release_after_settle_is_noop`.
  - `test_topup_same_provider_ref_twice_credits_once` (Review Focus 4).
  - `test_refund_after_spend_clamps_at_zero` (Review Focus 4).
  - `test_invariant_holds_after_random_ops` (property-style: 200 random ops, seeded).
  - `test_concurrent_reserves_never_overdraw` in `test_ledger_concurrency.py` (Review Focus 1): balance 5,000; 20 threads each reserve 1,000 with distinct request ids → exactly 5 succeed, 15 raise `InsufficientCredits`, available 0.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** with `SELECT ... FOR UPDATE` on `balances`, ledger insert + balance update in one transaction; idempotency via `UNIQUE(kind, ref)` and `ON CONFLICT DO NOTHING` returning the existing result. **Step 4: Run** → PASS (concurrency test included, under 2 s). **Step 5: Commit.**

### Task 4: Starter grant and tier rules (DONE, 8 tests; premium and starter-first rules live in `ledger.reserve/settle`, expiry skips accounts with open holds)

**Files:**
- Create: `billing/grants.py`, `tests/test_grants.py`
- Modify: `billing/ledger.py` (`reserve` checks tier)

**Interfaces:**
- Produces: `grant_starter(conn, account_id, today: date) -> GrantResult(granted: bool, reason: Literal["granted","already_granted","daily_cap"])`; `expire_starter(conn, now) -> int` (posts `adjust` with ref `starter-expiry:<account>` for the unspent starter remainder, returns count). Starter credits are tracked as `starter_micros` within `available_micros` and spent first on open aliases.
- Rule: `reserve` on a `premium` alias requires `available_micros - starter_micros >= amount`; otherwise `InsufficientCredits` with `premium_requires_purchase=True`.

- [ ] **Step 1: Tests**: `test_grant_once_per_account`; `test_daily_cap` (cap 2 → third account `daily_cap`); `test_expiry_removes_only_unspent_starter`; `test_premium_rejected_with_only_starter_credits` (Review Focus 5); `test_open_alias_spends_starter_first`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit.**

### Task 5: HTTP API and contract (DONE, 22 tests; contract at `contracts/billing.yaml`)

Contract changes made here: (1) `POST /v1/reservations` takes `lines: [{alias, max_input_tokens, max_output_tokens, calls}]` and billing prices them, so no other service does money arithmetic; (2) billing's 402 body is `{detail, balance_micros, required_micros, premium_requires_purchase}` and the app translates it into the learner-facing 402 shape; (3) `POST /v1/payments/topup` and `/refund` exist now for Plan 4's webhooks; (4) token auth covers `/v1/*` only, `/healthz` and `/metrics` are internal-network only.

**Files:**
- Create: `billing/api.py`, `billing/metrics.py`, `contracts/billing.yaml`, `services/billing/tests/test_api.py`, `services/billing/tests/test_contract.py`

**Interfaces:**
- Produces endpoints (bearer `BILLING_SERVICE_TOKEN`): `POST /v1/accounts/{id}` (ensure), `POST /v1/accounts/{id}/grants/starter`, `GET /v1/accounts/{id}/balance`, `GET /v1/accounts/{id}/history`, `POST /v1/reservations` `{account_id, request_id, action, alias, amount_micros}` → 201 or 402, `POST /v1/reservations/{request_id}/settle` `{usage: [Usage...]}` (billing prices the usage itself, so the app never computes money), `POST /v1/reservations/{request_id}/release`, `GET /v1/prices`, `POST /v1/estimate` `{alias, action, input_tokens, output_tokens}` → `{credits}`, `GET /healthz`, `GET /metrics`.
- Metrics: `billing_charged_micros_total{alias,action}`, `billing_margin_micros_total{alias}`, `billing_written_off_micros_total`, `billing_reservations_open`, `billing_insufficient_total{reason}`, `billing_starter_grants_total{result}`.

- [ ] **Step 1: Tests**: `test_requires_service_token` (401); `test_reserve_402_shape` (exact keys and `required_credits` rounded up); `test_settle_prices_usage_server_side`; `test_contract_matches_openapi` (`app.openapi()` equals `contracts/billing.yaml` loaded; regenerate with `python -m billing.api --dump-openapi`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit.**

### Task 6: App wiring: `metered(action)` on every model route

**Files:**
- Create: `app/billing_client.py`, `app/metered.py`, `tests/test_metered.py`, `tests/test_metered_routes.py`, `tests/support/fake_billing.py`
- Modify: `app/config.py` (`billing_enabled: bool = False`, `billing_base_url`, `billing_service_token: SecretStr`, `top_up_url`), `app/api.py` (routes at lines 280-480 and `_sse`), `app/coach.py`, `app/drawings.py`, `app/exports.py`, `app/api_models.py` (`EstimateResponse`), `frontend/src/api/client.ts` + types (handle 402 and show estimate)

**Interfaces:**
- Consumes: `metering_scope`, `UsageRecord` (Plan 1 Task 3); billing endpoints (Task 5).
- Produces:
  - `ACTION_MAX_CALLS: dict[str, int]` = `{"chat": 1, "code_chat": 1, "agent": 6, "quiz_generate": 3, "quiz_validate": 1, "quiz_explain": 1, "flashcards_generate": 3, "coach_start": 4, "coach_answer": 2, "coach_recap": 2, "export": 2, "drawing_review": 2, "kb_ingest": 1}`
  - `class BillingClient`: `reserve(account_id, request_id, action, alias, amount_micros)`, `settle(request_id, usage: list[UsageRecord])`, `release(request_id)`, `estimate(alias, action) -> int`, `prices() -> dict` (60 s cache).
  - `@contextmanager metered(action: str, alias: str) -> Iterator[Meter]`: no-op scope when billing disabled; otherwise reserve `ceiling(alias) × ACTION_MAX_CALLS[action] + guard ceiling × 3 × ACTION_MAX_CALLS[action]`, open a metering scope whose `on_add` raises `CreditsExhausted` once priced usage exceeds the reservation, settle in `finally` (release when no records).
  - `def metered_stream(action, alias, events: Iterator) -> Iterator` for SSE: wraps the generator so settle runs in its `finally` (covers client disconnect via `GeneratorExit`).
  - `CreditsExhausted` → SSE error frame `"Your credits ran out during this action. Top up to continue."`; HTTP 402 body per Global Constraints.
  - `GET /api/billing/balance`, `GET /api/billing/estimate?action=&model=` (app-facing, scoped to the caller's account).

- [ ] **Step 1: Tests** (`fake_billing.py` is an in-process fake of the contract):
  - `test_disabled_billing_is_noop` (no HTTP calls).
  - `test_route_reserves_then_settles_actual_usage`.
  - `test_402_when_reserve_refused` (exact body).
  - `test_failed_model_call_releases` (Plan 1 `ModelServiceUnavailable` → release, no settle).
  - `test_sse_disconnect_still_settles` (Review Focus 2: close the generator after first token → settle called with records so far).
  - `test_agent_stops_when_credits_exhausted` (Review Focus 3: fake usage crosses the reservation on call 3 → call 3 settled, call 4 never made, error frame text exact).
  - `test_every_model_route_is_metered` in `test_metered_routes.py`: enumerate `app.routes`; every POST route under `/api/chat`, `/api/code-chat`, `/api/agent`, `/api/quiz`, `/api/flashcards/generate`, `/api/coach`, `/api/drawings/*/ai-review`, `/api/exports`, `/api/kb/upload`, `/api/kb/scrape` produces a reserve call when invoked against fakes; a new unmetered model route fails this test.
  - Frontend Vitest: 402 shows balance, required credits and a Top up link; estimate renders "about N credits".
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** Keep `limits.consume()` as the rate limit; billing is separate. **Step 4: Run** `pytest tests -q && pytest services/billing/tests -q && (cd frontend && npm test)` → PASS. **Step 5: Commit.**

### Task 7: Sweeper and reconciler

**Files:**
- Create: `billing/jobs.py`, `tests/test_jobs.py`

**Interfaces:**
- Produces CLI `python -m billing.jobs sweep|expire|reconcile|check-prices --date YYYY-MM-DD`:
  - `check_prices(conn, model_info: list[dict]) -> list[PriceDiff]`: compares the current `prices` version with gateway `/model/info` per-token costs; any difference sets `billing_price_drift` gauge to 1 and logs the alias. Never reprices automatically (spec 15).
  - `sweep(conn, now) -> int`: release reservations `open` for > 15 min.
  - `expire`: calls `expire_starter`.
  - `reconcile(conn, spend_rows: Iterable[dict], day) -> ReconcileReport(matched, missing_in_ledger, drift_micros)`: joins LiteLLM spend logs (`metadata.request_id`, `user`, tokens) to settled reservations; for usage the ledger never charged, posts `adjust` with ref `reconcile:<litellm id>` (charge, clamped at zero), sets `billing_reconcile_drift_micros` gauge. Spend rows fetched from gateway `GET /spend/logs/v2?start_date=&end_date=&page=&page_size=` (optionally `end_user=`) with `GATEWAY_ADMIN_KEY`; join on `metadata.spend_logs_metadata.request_id` (the reservation's `request_id`) and `end_user` (workspace id). The legacy `/spend/logs` with dates returns daily summaries, not rows.

- [ ] **Step 1: Tests**: `test_sweep_releases_only_stale`; `test_reconcile_zero_drift_when_all_settled`; `test_reconcile_charges_missing_usage_once` (run twice → one adjust); `test_reconcile_ignores_other_apps` (rows whose key alias differs); `test_check_prices_flags_changed_alias_only`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit.**

### Task 8: Deploy wiring, dashboard and runbook

**Files:**
- Modify: `docker-compose.yml` (add `billing` + `billing-db` under profile `hosted`), `docker-compose.hosted.yml` (`BILLING_ENABLED=true`, URLs, tokens via `${...:?}`), `monitoring/` (Grafana billing panel: charged, margin, written-off, drift, open reservations; alert on drift > 0 and written-off > $1/day), `.github/workflows/quality.yml` (Postgres service, billing tests), `.env.example`
- Create: `engineering/runbooks/billing.md` (price publish, manual adjust, refund, reading drift alerts), cron entries for sweep (every 5 min), expire (hourly), reconcile (nightly)

- [ ] **Step 1:** `docker compose -f docker-compose.yml -f docker-compose.hosted.yml --profile hosted config` → valid.
- [ ] **Step 2:** End-to-end on staging with the Plan 1 gateway: grant starter, run one quiz, `GET /api/billing/balance` drops by the settled amount; next morning's reconcile reports drift 0.
- [ ] **Step 3:** `mkdocs build -f mkdocs-contributors.yml --strict` → PASS.
- [ ] **Step 4: Commit and push.**
