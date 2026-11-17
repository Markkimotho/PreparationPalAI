# Plan 3: Accounts (OIDC) and Postgres storage

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real learner accounts (email sign-in, Google, Apple) and multi-user storage, so the hosted app can serve many people safely and the free starter allowance cannot be farmed.

**Architecture:** A self-hosted Logto issues standard OIDC tokens. The app only verifies them (`app/oidc.py`) and maps the token subject to a private workspace id, so every existing engine keeps its workspace scoping. Hosted mode stores data in Postgres (one `app` schema, every row filtered by workspace) with pgvector replacing Chroma. Self-hosted mode keeps static keys, SQLite, JSON and Chroma unchanged.

**Tech Stack:** Python 3.11, FastAPI, PyJWT + cryptography, psycopg 3 pool, pgvector (`langchain-postgres`), Logto (pinned image), Postgres 16.

**Spec:** `specs/2026-11-17-hosted-product-design.md` (sections 7.2, 7.6, 8.4). **Builds on:** Plans 1 and 2 (merged in PR #20).

**Provider decision (ranked on 2026-11-17 repository data):** Logto (MPL-2.0, last commit today, 127 open issues, release v1.46.0 on 2026-11-05, light Node + Postgres). Second choice Zitadel (AGPL, 1,387 open issues, heavier). Rejected: Keycloak (JVM memory too large for a ~$30 server), Ory Kratos (no commits since 2026-07-29, headless so sign-in screens must be built), Authelia (a gateway, not an app sign-up system).

## Global Constraints

- `AUTH_MODE` is `tokens` (default, today's static keys) or `oidc`. `STORAGE_BACKEND` is `files` (default) or `postgres`. Defaults keep every existing test passing.
- The workspace id for an account is `u-` + the first 20 hex characters of `sha256(issuer + "|" + sub)`. It always matches `^[a-zA-Z0-9_-]{1,64}$` and is never derived from an email.
- Accept only RS256 or ES256 access tokens whose `iss` equals `OIDC_ISSUER`, `aud` contains `OIDC_AUDIENCE`, with `exp`, `iat` and `sub` present and 60 seconds of clock leeway. Never accept `alg: none` or any HMAC algorithm.
- Roles come from a token `roles` claim (`admin`, `editor`, `reader`); a missing claim means `editor`. Static-token roles are unchanged.
- The starter grant requires `email_verified: true`, one grant per normalized email, and a non-disposable domain.
- No secret in the repo: issuer client secrets and management credentials only via environment variables; Logto image pinned to an exact tag.
- Commit messages carry no Claude co-author line; push after every green task.

## Review Focus

1. Tokens that must be rejected, never mapped to a workspace: expired, not yet valid, wrong issuer, wrong audience, `alg: none`, HS256 signed with the public key as the secret, tampered payload, missing `sub`. Test in Task 1.
2. Signing-key rotation: an unknown `kid` triggers one rate-limited JWKS refetch; if the JWKS endpoint is down cached keys keep working for 24 hours; an unknown `kid` is still rejected. Test in Task 1.
3. Starter-credit farming: the same Gmail written with dots or `+tag`, upper case, an unverified email, or a disposable domain gets no second grant. Test in Task 3.
4. Account deletion twice, or while a request is in flight: idempotent, every store is emptied, billing refuses new reservations but keeps an anonymous ledger. Test in Task 4.
5. Cross-user reads in Postgres: user A can never list, read, update or delete user B's rows in any store, including vector search. Test in Tasks 6 and 7.

---

### Task 1: Verify OIDC tokens (`app/oidc.py`) (DONE, 22 tests, 0.9s)

**Files:** Create `app/oidc.py`, `tests/test_oidc.py`, `tests/support/fake_issuer.py`. Modify `requirements.txt`, `pyproject.toml` (add `pyjwt[crypto]>=2.8`).

**Interfaces:**
- Produces `@dataclass(frozen=True) Principal(workspace: str, identity: str, role: str, email: str | None, email_verified: bool, subject: str)`.
- Produces `class TokenRejected(Exception)` with a short `reason` string that is safe to log (never the token).
- Produces `def verify_token(token: str) -> Principal` using `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` (default `<issuer>/jwks`) from settings.
- Produces `def workspace_for(issuer: str, subject: str) -> str`.
- Produces `fake_issuer.py`: `FakeIssuer` that generates an RSA key, serves a JWKS over an in-process server, and `sign(claims, kid=..., alg=...)`; supports `rotate()`.

- [ ] **Step 1: Write failing tests** in `tests/test_oidc.py`: `test_valid_token_maps_to_a_stable_private_workspace`; parametrized `test_rejected_tokens` for every case in Review Focus 1; `test_roles_claim_defaults_to_editor`; `test_unknown_kid_refetches_once_then_accepts_after_rotation`; `test_unknown_kid_is_rejected_when_refetch_does_not_help`; `test_refetch_is_rate_limited` (ten bad-kid tokens cause at most one extra fetch); `test_cached_keys_survive_a_jwks_outage_for_24h_and_no_longer` (monkeypatched clock); `test_workspace_id_never_contains_the_email`.
- [ ] **Step 2: Run** `pytest tests/test_oidc.py -q` → FAIL.
- [ ] **Step 3: Implement** with `jwt.PyJWKClient`-style caching written by hand (own cache dict, lock, clock injection) so rotation and outage rules are explicit.
- [ ] **Step 4: Run** → PASS. **Step 5: Commit and push.**

### Task 2: Accept OIDC tokens in workspace auth (DONE, 13 tests; `/api/auth/status` now also returns `mode` and `issuer`)

**Files:** Modify `app/config.py` (`auth_mode`, `oidc_issuer`, `oidc_audience`, `oidc_jwks_url`; validator), `app/auth.py` (`WorkspaceAuth`), `tests/test_auth.py`; Create `tests/test_auth_oidc.py`.

**Interfaces:** Consumes `verify_token`. Produces: in `oidc` mode every `/api/*` route except `/api/auth/status` requires a valid bearer JWT; `workspace_id`, `identity_id` and `role` are set from the `Principal`; `GET /api/auth/me` adds `email_verified` and `mode`. `GET /api/auth/status` returns `{enabled, mode, issuer}` so clients know where to sign in.

- [ ] **Step 1: Tests:** valid token reaches a route as workspace `u-…`; two tokens for two subjects get different workspaces and cannot see each other's flashcards; rejected token gives 401 with `WWW-Authenticate: Bearer error="invalid_token"` and no reason text; `reader` role cannot mutate; `/metrics` and model pulls stay admin-only; `tokens` mode behaves exactly as before; `AUTH_MODE=oidc` without issuer or audience fails settings validation; `production` still requires auth.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** full suite → PASS. **Step 5: Commit and push.**

### Task 3: Starter grants only for verified, distinct people (DONE, 18 billing + 3 app tests)

A refused attempt changes nothing (savepoint): it neither uses the daily cap nor burns the mailbox. `BILLING_REQUIRE_VERIFIED_EMAIL=false` exists for deployments without accounts (tests default to it, and `tests/test_emails.py` switches it on).

**Files:** Billing: Create `services/billing/billing/migrations/004_email_keys.sql` (`billing.grant_emails(email_key TEXT PRIMARY KEY, account_id TEXT, created_at)`), `billing/emails.py`, `billing/disposable_domains.txt`, `tests/test_emails.py`; Modify `billing/grants.py`, `billing/api.py` (`POST /v1/accounts/{id}/grants/starter` takes `{email, email_verified}`), regenerate `contracts/billing.yaml`. App: Modify `app/metered.py` (`_ensure_started` passes the principal's email), `app/billing_client.py`.

**Interfaces:** Produces `def email_key(email: str) -> str` (lower-case, Gmail and Googlemail dots removed, `+tag` removed, then sha256 hex) and `def is_disposable(email: str) -> bool`. `grant_starter(conn, account_id, today, email=None, email_verified=False, cap=None)` returns reasons `granted | already_granted | daily_cap | email_unverified | email_in_use | disposable_email`.

- [ ] **Step 1: Tests** for each reason and for Review Focus 3 (`a.b+x@gmail.com` and `ab@googlemail.com` map to one key; a second account with that key gets `email_in_use` and nothing credited; a failed attempt does not consume the daily cap). **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** billing and app suites → PASS. **Step 5: Commit and push.**

### Task 4: Delete an account (DONE for the file-based stores, 19 app + 5 billing tests)

`DELETE /api/account` closes billing first (if billing is down nothing is deleted and the learner retries), purges every store through the registry in `app/purge.py`, then removes the Logto user last. Billing keeps the anonymous ledger and a tombstone so a closed account cannot be resurrected; the one-way mailbox key stays so deleting and re-registering cannot farm another free allowance. Remaining purchased credits are forfeited on deletion, so the sign-out screen in Plan 4 must show the balance and warn. The Postgres stores in Tasks 6 and 7 register their own deleters.

**Files:** Create `app/account.py`, `app/purge.py`, `tests/test_account_deletion.py`; Billing: add `ledger.close_account(conn, account_id)` and `POST /v1/accounts/{id}/close`, migration `005_account_closed.sql`.

**Interfaces:** `purge.register(name: str, fn: Callable[[str], int])` and `purge.purge_workspace(workspace: str) -> dict[str, int]` run every registered store's deleter (each later store task registers its own). `DELETE /api/account` purges the workspace, closes the billing account, and (when `LOGTO_MANAGEMENT_*` is configured) asks Logto to delete the user; it returns 204 and is idempotent. Billing keeps ledger rows (anonymous) but reserve on a closed account returns 403.

- [ ] **Step 1: Tests** for Review Focus 4 using fake stores; two deletes in a row; deletion while a hold is open releases it first; billing 403 after close. **Step 2–5:** run red, implement, run green, commit and push.

### Task 5: Postgres layer and app schema (DONE, 12 tests)

Test database: `docker compose -f tests/support/docker-compose.pg.yml up -d` (pgvector/pgvector:pg16, 127.0.0.1:15433); tests skip cleanly when it is not running. `chunks.embedding` is fixed at `vector(1024)` (HNSW, cosine), matching the gateway's Matryoshka size.

**Files:** Create `app/db.py`, `app/migrations/001_app.sql` (schema `app`; tables `flashcard_decks`, `coach_sessions`, `drawings`, `ingestion_jobs`, `usage_events`, all with `workspace TEXT NOT NULL` and an index starting with `workspace`), `app/migrate_db.py`, `tests/test_app_db.py`, `docker-compose.test.yml` fixture for Postgres+pgvector (`pgvector/pgvector:pg16`).

**Interfaces:** `db.configure(url)`, `db.transaction() -> ContextManager[Connection]` (dict rows), `db.enabled() -> bool` (true when `STORAGE_BACKEND=postgres`), `migrate_db.apply() -> list[str]`. New setting `DATABASE_URL`.

- [ ] Tests: migrations apply twice idempotently; every table has a non-null `workspace` and a workspace-leading index (read from `information_schema`/`pg_indexes`); pool survives a dropped connection. Run red, implement, run green, commit and push.

### Task 6: Move the per-user stores to Postgres

**Files:** Modify `app/flashcards.py`, `app/coach.py`, `app/drawings.py`, `app/jobs.py`, `app/limits.py`; each keeps its public functions and switches on `db.enabled()`. Create `tests/test_postgres_stores.py` and `tests/support/pg.py` (fixture that skips when Postgres is unavailable and CI provides it).

**Interfaces:** No public signature changes. Job claiming becomes `SELECT … FOR UPDATE SKIP LOCKED`; rate limiting uses one `INSERT … ON CONFLICT` counter per (workspace, identity, minute). Each store registers a `purge` deleter.

- [ ] For each store: run the store's **existing** test file against Postgres (parametrized fixture `backend in {files, postgres}`), add the two-user isolation test from Review Focus 5, and a concurrency test for job claiming (ten workers, one job, one winner). Commit and push after each store.

### Task 7: pgvector instead of Chroma in hosted mode (DONE, 11 tests)

`get_vectorstore()` returns a `PgVectorStore` when `STORAGE_BACKEND=postgres`; ingest, clear, counts, sources, readiness and purge all branch on it. Verified on real Postgres: with selective workspace filters the planner uses an exact btree plan, so results are complete; `hnsw.iterative_scan` is set so the HNSW plan stays correct for a very large tenant.

**Files:** Create `app/pgvector_store.py`, `app/migrations/002_vectors.sql`, `tests/test_pgvector_store.py`; Modify `app/vectorstore.py`.

**Interfaces:** `get_vectorstore()` returns an object with the calls the app already makes (`add_documents`, `similarity_search`, `as_retriever`, `delete` by source, counts, source listing) backed by `app.chunks(workspace, collection, source, page, content, embedding vector(N), metadata jsonb)` with an HNSW index. `N` comes from the embedding model (`EMBEDDING_DIMENSIONS`, 1024 recommended; the plan's first step verifies that the provider honours it).

- [ ] Tests: add/search/delete round trip; dedupe by deterministic chunk id; Review Focus 5 for vector search (user B's query never returns user A's chunks, even with identical text); a second embedding model uses a separate `collection`; `ingest_documents` keeps recording embed usage. Commit and push.

### Task 8: Run Logto and document sign-in

**Files:** Modify `docker-compose.hosted.yml` (services `logto` pinned, `logto-db`), `tests/test_hosted_compose.py`, `.env.example`; Create `engineering/runbooks/accounts.md`; update `mkdocs-contributors.yml`.

- [ ] Compose tests: Logto and its database publish no host ports (only the proxy fronts them), memory limits set, image pinned. Runbook covers one-time console setup (API resource audience, a web application, a native application with `expo-auth-session` redirect, email OTP connector, Google and Apple connectors), roles, and account deletion. Strict docs build passes. Commit and push.

### Task 9: Live end-to-end check

- [ ] With a fake issuer (generated keys) plus the real app, real billing, real LiteLLM and Postgres/pgvector: sign in as two users, chat, upload and search a document, buy credits through the billing API, delete one account, and confirm the other's data and balance are untouched and reconcile reports zero drift. Record results in this plan and commit.
