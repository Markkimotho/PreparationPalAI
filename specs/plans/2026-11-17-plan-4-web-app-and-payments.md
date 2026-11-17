# Plan 4: Installable web app, sign-in and payments

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A learner can open the hosted site, install it as an app, sign in, see their balance and history, buy credits through a merchant of record, and delete their account, with every purchase credited exactly once.

**Architecture:** Billing owns money end to end: it lists packs, creates the Paddle transaction for a checkout, and receives Paddle's signed webhooks on one public path (`/webhooks/paddle`, routed by the proxy straight to billing). The app only relays checkout requests for the signed-in learner. The web client signs in with `@logto/browser` behind one small module, opens Paddle's overlay checkout for the transaction billing created, and installs as a PWA with a service worker that caches only the app shell.

**Tech Stack:** FastAPI, psycopg, httpx (billing); React 18 + Vite + TypeScript, `@logto/browser` 3.x, Paddle.js v2 (web); plain service worker; Caddy.

**Spec:** `specs/2026-11-17-hosted-product-design.md` (sections 7.5, 8.3, 9). **Builds on:** Plans 1 to 3 (PR #20).

**Decisions (2026-11-17):** Paddle first (merchant of record; selling entity approval deferred by Mark). Webhook signatures verified as documented by Paddle: `Paddle-Signature: ts=…;h1=…`, HMAC-SHA256 over `ts + ":" + raw_body` with the destination's secret, any matching `h1` accepted (secret rotation), timestamp tolerance configurable (default 300 s). Web sign-in uses `@logto/browser` (3.1.2, MIT, released 2026-10-26) rather than `oidc-client-ts` (last release 2026-03-13), wrapped in `src/auth/session.ts` so the provider can change in one file.

## Global Constraints

- Packs (spec 8.3, web prices): `web-5` $5 = 5,000 credits; `web-10` $10 = 10,500; `web-20` $20 = 21,500; `web-50` $50 = 55,000. Credits granted come from billing's pack table, never from webhook amounts.
- A purchase is credited once per Paddle transaction id; a refund or chargeback is applied once per adjustment id and never takes a balance below zero.
- Only `/webhooks/paddle` on billing is public. Every other billing route keeps the service token.
- No secret reaches the browser except Paddle's client-side token (designed to be public).
- The service worker never caches `/api/`, `/auth/`, `/webhooks/` or non-GET requests.
- Commit messages carry no Claude co-author line; push after every green task.

## Review Focus

1. A webhook with a bad, missing, stale or replayed signature is rejected (401) and credits nothing. Test in Task 1.
2. Paddle retries `transaction.completed` five times: credited once. Test in Task 1.
3. A partial refund, then a second partial refund, then a chargeback: each applied once, proportionally, clamped at zero. Test in Task 1.
4. A purchase for an unknown price or a missing account id: not credited, logged and counted, still answered 200 so Paddle stops retrying. Test in Task 1.
5. An expired sign-in in the web app: the next API call gets 401, the app returns to the sign-in screen instead of failing silently. Test in Task 3.

---

### Task 1: Billing — packs, Paddle checkout, signed webhooks (billing service) (DONE, 26 tests)

Files: `billing/packs.py`, `billing/paddle.py`, `billing/api.py`, `billing/settings.py`, `billing/ledger.py` (refund per adjustment), tests `tests/test_paddle.py`, contract regenerated.

### Task 2: App — packs, checkout and history for the signed-in learner

Files: `app/api.py`, `app/billing_client.py`, `app/metered.py` (exempt routes), tests `tests/test_billing_web.py`.

### Task 3: Web sign-in

Files: `frontend/src/auth/session.ts`, `frontend/src/api/access.ts`, `frontend/src/components/AccessGate.tsx`, tests.

### Task 4: Account page — balance, history, buy credits, delete account

Files: `frontend/src/sections/Account.tsx`, `frontend/src/api/billing.ts`, `frontend/src/payments/paddle.ts`, route and navigation, tests.

### Task 5: Installable app (PWA)

Files: `frontend/public/manifest.webmanifest`, icons, `frontend/public/sw.js`, `frontend/public/sw-strategy.js`, `frontend/index.html`, `frontend/src/pwa/register.ts`, `app/api.py` (MIME types, no-cache for the worker), tests.

### Task 6: Deploy, docs and end-to-end

Files: `deploy/Caddyfile.hosted` (public webhook path), `docker-compose.hosted.yml` (Paddle settings), `engineering/runbooks/payments.md`, tests; a signed-webhook end-to-end run against the live stack.
