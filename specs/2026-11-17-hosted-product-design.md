# PreparationPalAI as a hosted, pay-per-use product

Status: draft for approval · Date: 2026-11-17 · Owner: Mark

This spec lives outside `docs/` and `engineering/` on purpose: both are published
MkDocs sites, and pricing and business plans should not go public.

## 1. Intent

PreparationPalAI today is a self-hosted study and interview-prep workspace: React SPA,
FastAPI, Ollama, Chroma, SQLite, static bearer keys. Mark wants it to become a product
anyone in the world can use:

- in the browser, as an installable desktop/web app, and as a native app downloaded
  from the Google Play Store and Apple App Store;
- hosted on a VPS, not on the learner's machine;
- paid for by usage, so learners cover hosting and model cost plus a small margin for
  maintenance. Profit is not the goal; sustainability is;
- open models first (GLM, Qwen), with optional premium models (Claude, OpenAI, Grok)
  for users who want them;
- all model traffic through Mark's own AI gateway, which his other AI apps will share.

Mark is in Kenya; users are worldwide.

## 2. Goals, non-goals, anti-goals

**Goals**
1. A learner can sign up on web, Android or iOS, get a free starter allowance, study,
   top up, and keep one balance across all three.
2. Every model call is metered and charged from the real token usage of the model used.
3. Fixed monthly costs stay small (one VPS) and model cost is zero when nobody studies.
4. One AI gateway, separate from this app, that other apps can join with their own key.
5. Self-hosted mode keeps working: `docker compose up` with Ollama, no billing, no accounts.

**Non-goals (v1)**
- Subscriptions, team or classroom plans, invoicing, coupons.
- Running our own GPUs. Revisit only when volume makes it cheaper than per-token APIs.
- Offline study on phones beyond cached flashcards.
- Multi-region or Kubernetes.

**Anti-goals (failure even if it "works")**
- A user is charged for a call that failed, or a call runs without being charged.
- Balance can go negative through concurrent requests.
- Payment or tax obligations Mark cannot meet from Kenya.
- An app store rejection loop because of payment rules or missing account deletion.
- A free allowance that bots can farm into a real bill.

## 3. Decisions

Decided by Mark in conversation:
- Native mobile app published to both stores (not only an installable web app).
- Pay-per-use with prepaid credits.
- New users get a free allowance.
- Approach A: self-hosted VPS, self-hosted LiteLLM gateway, Postgres + pgvector,
  billing service owned by us, Expo app.

My calls, open to correction (marked **[call]** below where they appear):
- Expo (React Native) for the native app, TypeScript shared with the web client.
- Merchant of record for worldwide card payments; Paystack added later for M-Pesa.
- Hosted per-token APIs (OpenRouter plus direct provider keys) for open models.
- 1 credit = $0.001 of list price; multipliers 1.5x open, 1.25x premium.
- Free allowance of 500 credits ($0.50), open models only, after email verification.
- Hetzner Cloud VPS behind Cloudflare; GitHub Actions to GHCR to the VPS.

CLAUDE.md note: the "no LLM APIs" rule yields here because Mark explicitly asked for
hosted Claude, OpenAI, Grok, GLM and Qwen models routed through his gateway.

## 4. Constraints found in the current code

| Area | Today | Consequence |
| --- | --- | --- |
| Inference | Ollama only: `app/llm.py` (`GuardedChatOllama`), `app/embeddings.py`, `app/safety.py`, `app/model_catalog.py`, `app/analysis.py` | One provider-neutral model factory pointing at the gateway |
| Guard passes | Each generation runs moderation on input, moderation on output, and `verify_response` | About 3 model calls per user action; they must be metered and run on a cheap model |
| Identity | Static `AUTH_TOKENS` digests mapped to workspace + role (`app/auth.py`) | Real accounts are new; the `workspace_id` / `identity_id` context vars can stay as the scoping seam |
| Budgets | `app/limits.py` counts requests per identity in SQLite | Keep as an abuse rate limit; money moves to the ledger |
| Storage | Chroma per workspace, JSON flashcards, SQLite coach/jobs/usage, files under `data/` | Single-host only; move to Postgres + pgvector for multi-user |
| Frontend | React 18 + Vite SPA, responsive, no manifest or service worker | Web becomes installable with a manifest; native app is new |
| Heavy UI | Excalidraw drawing, KaTeX maths, highlight.js | No native equivalents; reuse web components inside the native app |

## 5. Approaches considered

| | A. VPS + own LiteLLM gateway (chosen) | B. Managed (Supabase + Fly/Render) | C. OpenRouter direct, no gateway |
| --- | --- | --- | --- |
| Fixed cost | Lowest (~$30-45/month all-in) | 2-4x higher | Lowest |
| Ops load | Mark runs server, backups, upgrades | Least | Low |
| Shared gateway for other apps | Yes | Yes | No, rebuilt later |
| Vendor dependence | Low | High | Medium |

Mark picked A. Rejected outright: a hand-written gateway (LiteLLM already does routing,
per-app keys, cost maps and spend logs) and self-hosted GPUs (idle cost breaks
pay-per-use at low volume).

## 6. Architecture

```text
 Android / iOS (Expo)     Web + installable PWA (existing React app)
          \                     /
           \  HTTPS, OIDC tokens
            v                   v
   Cloudflare (DNS, TLS, WAF, rate limits)
            |
   Caddy on Hetzner VPS
     |-- app        FastAPI (existing app/), study engines, SSE
     |-- worker     ingestion jobs (existing jobs.py)
     |-- billing    services/billing: ledger, prices, payments webhooks
     |-- auth       self-hosted OIDC provider (see 7.2)
     |-- postgres   app data + pgvector + billing schema (separate schemas, separate roles)
     |
     '-- ai-gateway (separate repo, separate Compose project)
           LiteLLM proxy + its own Postgres
             -> OpenRouter, Z.ai (GLM), Alibaba Model Studio (Qwen),
                Anthropic, OpenAI, xAI
Payments: merchant of record webhooks, RevenueCat webhooks (stores), Paystack (later)
```

Repository layout (services-first, per CLAUDE.md):

```text
PreparationPalAI/
  app/                  existing API + engines (gains a gateway model factory)
  frontend/             existing web app (gains PWA manifest, billing screens)
  mobile/               NEW Expo app
  services/billing/     NEW billing service: own code, tests, evals, README, Dockerfile
  contracts/            NEW OpenAPI for app API and billing API; generated TS client
  deploy/               Compose files, Caddyfile, backup scripts
ai-gateway/             NEW separate repo: LiteLLM config, Compose, key admin scripts
```

## 7. Components

### 7.1 AI gateway (`ai-gateway` repo)

- LiteLLM proxy with its own Postgres for keys and spend logs. Deployed as its own
  Compose project on the same VPS at first, reachable only on a private Docker network
  plus an authenticated admin route. It can move to its own host later without app changes.
- One virtual key per app (`preparationpal-prod`, `preparationpal-staging`, later
  other apps), each with a monthly hard budget as a circuit breaker.
- Model aliases decouple apps from providers: `open-default` (GLM), `open-fast` (Qwen
  small), `open-reasoning`, `guard` (small Qwen for moderation and verification),
  `vision-open` (GLM vision for drawing review), `embed-default`, `premium-claude`,
  `premium-gpt`, `premium-grok`. Fallbacks per alias (for example GLM via Z.ai first,
  OpenRouter second).
- Apps pass `user=<account id>` and metadata `{action, request_id}` on every call so
  spend logs can be joined to the ledger.
- Cost source: the gateway returns token `usage` (with `stream_options.include_usage`
  for streams). LiteLLM's `x-litellm-response-cost` header is not sent on streaming
  responses (reported in LiteLLM issue #12689), so billing computes cost from usage
  and its own price table, and reconciles nightly against LiteLLM spend logs.

### 7.2 Accounts

- Users sign in with email one-time code, Google, and Apple. Sign in with Apple is
  required on iOS when other social logins are offered (App Store guideline 4.8).
- **[call]** Self-hosted OIDC provider rather than hand-rolled auth. Plan step 1
  evaluates Logto, Zitadel and Ory Kratos on stars, release recency, Expo support and
  RAM footprint, then records the pick. The app only validates JWTs.
- Each account maps to a personal workspace. The auth middleware sets the existing
  `workspace_id` and `identity_id` context vars from the token, so engines keep their
  scoping logic. Static keys stay for self-hosted mode.
- In-app account deletion that removes study data and closes the balance (App Store
  guideline 5.1.1(v), Play data deletion policy).

### 7.3 Billing service (`services/billing/`)

Owns money. Nothing else writes balances.

**Data model (Postgres, `billing` schema, integer micro-dollars, never floats)**
- `accounts(id, user_id, created_at)`
- `ledger(id, account_id, amount_micros, kind, ref, price_version, created_at)` where
  kind is `grant | topup | reserve | settle | release | refund | adjust`. Append-only.
- `balances(account_id, available_micros, reserved_micros, version)` updated in the
  same transaction as the ledger row, with `SELECT ... FOR UPDATE`.
- `prices(version, model_alias, input_per_m, output_per_m, cache_read_per_m,
  multiplier, effective_from)`. Every charge records the version used.
- `payments(id, provider, provider_ref UNIQUE, account_id, gross, net, currency,
  credits, status)`. Unique provider ref makes webhooks idempotent.

**Metering flow (reserve, then settle)**
1. App asks billing to reserve for `request_id`: estimated input tokens x input price
   + `max_output_tokens` x output price + guard estimate, times multiplier. Rejects with
   402 and a top-up link if `available < reserve`.
2. App calls the gateway.
3. App reports actual usage for every model call in that action (main and guard).
   Billing settles the real amount and releases the rest in one transaction.
4. If the call failed before any tokens were produced, release in full. Partial streams
   are charged for tokens actually produced.
5. Reservations older than 15 minutes are auto-released by a sweeper; the gateway's
   spend logs catch any usage that missed settlement, and the nightly reconciler posts
   an `adjust` and alerts.

API (contract in `contracts/billing.yaml`): `POST /reserve`, `POST /settle`,
`POST /release`, `GET /balance`, `GET /history`, `POST /webhooks/{provider}`,
`GET /prices`. Internal only, called by the app with a service token.

### 7.4 App changes (`app/`)

- Replace `GuardedChatOllama` with a `GuardedChatModel` built on an OpenAI-compatible
  client pointed at the gateway (`langchain-openai` `ChatOpenAI`, base URL = gateway).
  Keep the Ollama path behind `INFERENCE_BACKEND=ollama|gateway` for self-hosting.
- Guard passes call the `guard` alias, not the user's chosen model. Measure whether
  `verify_response` earns its cost per surface; that is an eval question, not a guess.
- Embeddings through `embed-default`. Re-embedding existing Chroma data happens in the
  migration (7.6).
- Model catalogue comes from the gateway's `/models` plus a local metadata table
  (label, tier, price per typical action). Remove Ollama pull UI in hosted mode.
- Every model-backed route wraps reserve and settle. A single decorator/context manager
  so no route can forget it, with a gate test that enumerates routes and fails if a
  model route lacks metering.
- Before an action runs, the UI shows its estimated credits ("about 14 credits").

### 7.5 Web app (`frontend/`)

- Add `manifest.webmanifest`, icons, and a service worker that caches the app shell
  only (never API responses) so it installs on desktop and Android Chrome.
- New screens: sign in, balance and history, top-up (redirect to merchant-of-record
  checkout), model tier picker with prices, account deletion.
- Shared code with mobile: generate the TypeScript API client from `contracts/` and
  publish it as a local package used by both apps.

### 7.6 Storage migration

- Postgres 16 + pgvector replaces Chroma (`chunks(workspace, source, embedding, ...)`),
  JSON flashcards, and the SQLite coach, jobs and usage stores. Job claiming moves to
  `SELECT ... FOR UPDATE SKIP LOCKED`.
- Uploaded files and drawings: local volume first, nightly encrypted backup to
  Cloudflare R2 or a Hetzner Storage Box.
- One-off migration script for any existing self-hosted workspace that wants to move
  in; fresh hosted users start empty.

### 7.7 Native app (`mobile/`, Expo)

- Expo Router, TypeScript, shared API client, OIDC via `expo-auth-session`, tokens in
  `expo-secure-store`.
- Native screens: sign in, home, Preparation Coach, Quiz Prep, flashcards (cached for
  offline review), Regular Chat, Study Agent, Programming Assistant, balance, top-up,
  settings, account deletion.
- Excalidraw drawing answers and KaTeX maths render through Expo DOM components
  (`"use dom"`), reusing the web React code. Native rewrite only if performance demands it.
- SSE: POST-based streaming with bearer tokens via `fetch` streaming (`expo/fetch`),
  mirroring `frontend/src/api/stream.ts`.
- Upload PDFs and images via `expo-document-picker` and `expo-image-picker`.
- Builds and store submission with EAS Build and EAS Submit; over-the-air JS fixes with
  EAS Update.
- **[call]** In-app purchases through RevenueCat (handles StoreKit and Play Billing
  receipts; webhooks credit the billing ledger). Verify its current free tier at setup.

## 8. Pricing model

### 8.1 Unit and formula

- 1 credit = $0.001 of list price. Balances shown in credits, with a dollar equivalent.
- `charge = (input_tokens x input_price + output_tokens x output_price
  + guard tokens x guard price) x multiplier`, rounded up to the micro-dollar.
- Multiplier: **1.5x** open models (covers hosting, payment fees, upkeep); **1.25x**
  premium models (larger base cost, so a smaller multiplier still covers fees).
- Embeddings and OCR are charged per upload at the same formula; at current embedding
  prices a 100-page PDF costs a fraction of a credit, so uploads feel free.

### 8.2 What an action costs (indicative, from `scripts/pricing_model.py`)

Provider prices used: GLM-4.6 $0.43/$1.75, Qwen3-14B $0.12/$0.24,
Qwen3-235B-A22B $0.23/$2.30 per million input/output tokens (OpenRouter, Nov 2026).
Guard passes on Qwen3-14B.

| Model | Chat turn | 10-question quiz | Coach exam grading |
| --- | --- | --- | --- |
| Qwen3-14B (open-fast) | 2.4 credits | 4.5 credits | 3.3 credits |
| GLM-4.6 (open-default) | 6.3 credits | 13.9 credits | 9.4 credits |
| Qwen3-235B (open-reasoning) | 5.4 credits | 13.6 credits | 8.9 credits |

So $5 buys roughly 360 GLM quizzes or 790 GLM chat turns. Premium prices are computed
from the gateway price table at launch, not hard-coded here.

### 8.3 Top-up packs

| Web (merchant of record) | Credits | In-app (store) | Credits |
| --- | --- | --- | --- |
| $5 | 5,000 | $4.99 | 5,000 |
| $10 | 10,500 | $9.99 | 10,000 |
| $20 | 21,500 | $19.99 | 20,000 |
| $50 | 55,000 | $49.99 | 50,000 |

Why: at $5, a merchant of record keeps 5% + $0.50, which nets $4.25, the same as a 15%
store fee (Apple Small Business Program, Google's first-$1M tier). Larger web packs net
90-94%, so web gets a bonus instead of the store being priced higher. The store price
for the same credits stays identical, which avoids review friction.

### 8.4 Free allowance

- 500 credits on email verification, open models only, expires after 30 days.
- One grant per verified email, per device ID (mobile), and capped per IP range per
  day; Cloudflare Turnstile on web sign-up. Disposable email domains blocked.
- Worst-case provider cost per grant is $0.33. A global daily cap on total grants
  stops a farming attack from turning into a bill.
- App Store reviewers use a demo account with credits, provided in review notes.

### 8.5 Break-even

Fixed costs about $43/month (VPS ~$30, Apple developer fee $99/year, domain and
backup storage ~$5). With 1.5x on open models and ~10% blended payment fees:

| Monthly user top-ups | Net after model cost, fees, fixed |
| --- | --- |
| $100 | -$20 |
| $250 | +$15 |
| $500 | +$73 |
| $1,000 | +$190 |

Break-even is about $185/month of top-ups. Multipliers are config in the `prices`
table, so they can move without a deploy; any change applies to new charges only and
is announced on the pricing page.

## 9. Payments and stores

- **Web, worldwide:** merchant of record (**[call]** Paddle first; Polar, Lemon Squeezy
  or Dodo Payments as fallbacks). It is the legal seller, handles VAT, GST and US sales
  tax, and pays out to Mark. Plan step 1 confirms Kenya payout eligibility during
  account approval; if Paddle declines, try the fallbacks in order.
- **Africa (phase 6):** Paystack Kenya for M-Pesa (1.5%) and cards, settling in KES or
  USD. Tax handling there is Mark's, so it starts with Kenya and nearby markets only.
- **iOS:** consumable in-app purchases are the default. US storefront apps may also
  link out to web checkout (Apple guideline 3.1.1(a), May 2025 revision); other
  storefronts may not without an entitlement. v1 ships in-app purchase everywhere and
  adds a US-only web link later if worth it.
- **Android:** Play Billing for in-app; Google's 2026 billing-choice programs differ by
  region. v1 uses Play Billing only.
- **One balance:** every rail posts a `topup` ledger row keyed by its provider
  reference. Credits bought anywhere work everywhere.
- **Refunds:** follow the merchant of record's and stores' rules; a refund webhook
  posts a negative `refund` row, and if credits are already spent, the account is held
  at zero rather than going negative.

## 10. Deployment channel

**Recommendation: Hetzner Cloud VPS, Cloudflare in front, GitHub Actions to GHCR.**

- Hetzner gives the most RAM and CPU per dollar, hourly billing, snapshots, and
  regions in the EU, US and Singapore. Start with one 4 vCPU / 8 GB instance in
  Falkenstein or Helsinki (good latency to Europe and East Africa); move the gateway
  to its own small instance when a second app joins.
- Cloudflare free plan: DNS, TLS, DDoS protection, Turnstile, and rate limits at the edge.
- CI: tests and evals gate on GitHub Actions; images push to GHCR; deploy by SSH
  running `docker compose pull && docker compose up -d` with health checks and
  automatic rollback to the previous tag on failure.
- Environments: `staging` (separate Compose project and gateway key, test payment
  mode) and `production`.
- Backups: nightly `pg_dump` and file volumes to off-site storage, restore tested
  monthly with the existing backup scripts adapted.
- Mobile: EAS Build and Submit to TestFlight / Play internal testing, then production.
- Observability: existing Prometheus, Grafana and Loki stack, plus billing metrics.

Accounts Mark needs: Hetzner, Cloudflare, GHCR (exists), Apple Developer ($99/year),
Google Play Console ($25 once), Expo, merchant of record, RevenueCat, model providers
(OpenRouter, Z.ai, Alibaba Model Studio, Anthropic, OpenAI, xAI), later Paystack.

## 11. Privacy and compliance

- Privacy policy and terms (needed by both stores and the merchant of record): what is
  stored, which model providers receive study text, retention, deletion.
- Kenya Data Protection Act 2019 (register as a data controller with the ODPC if
  thresholds apply) and GDPR for EU users. Model providers that train on API data are
  excluded or disclosed per alias.
- Content safety: keep the existing moderation and upload safety pipeline.

## 12. Measurable outcomes and traces

| Outcome | Metric | Trace |
| --- | --- | --- |
| Billing is exact | Nightly ledger vs LiteLLM spend drift = 0 micros; unbilled model calls = 0 | Reconciler job, alert on any drift |
| Sustainable | Gross margin per action by alias; monthly net vs fixed cost | `billing_margin_micros` metric, Grafana panel |
| People can start | Sign-up to first study action within 10 minutes | Funnel events |
| Free tier converts | % of verified users who top up within 30 days | Funnel events |
| Free tier not abused | Grants per day vs cap; grants per IP/device | Alerts |
| Usable on phones | Store approval; crash-free sessions > 99% | EAS / store consoles |
| Responsive | p95 time to first token per alias | Gateway + app metrics |

## 13. Testing and evals

Gate tests (fast, deterministic, every commit):
- Billing: reserve/settle/release arithmetic, concurrent reserves never overdraw
  (parallel transactions against a test Postgres), idempotent webhooks, refund at zero
  balance, price-version pinning, rounding.
- Route coverage: every model-backed route is metered (enumerated test).
- Gateway factory: request shape, alias mapping, usage extraction for streamed and
  non-streamed responses, using a stub OpenAI-compatible server.
- Auth: JWT validation, workspace scoping, cross-account isolation (port the existing
  cross-workspace tests).
- Mobile: Jest + React Native Testing Library for screens and the stream parser.
- Pricing: `scripts/pricing_model.py` has unit tests; docs tables are regenerated from it.

Periodic evals (paid, before ship and nightly):
- Existing coach, quiz and code evals run per open alias; a model alias cannot become
  a default unless it passes the threshold.
- Guard eval: moderation and verification quality on the `guard` alias, plus a
  cost-versus-catch-rate report for `verify_response`.
- Estimate accuracy: reserved vs settled ratio per action stays within bounds.

## 14. Phases and parallel workstreams

| Phase | Deliverable | Runs in parallel with |
| --- | --- | --- |
| 0 | Accounts opened (Hetzner, Cloudflare, Apple, Google, Expo, merchant of record approval incl. Kenya payout check, providers) | 1, 2 |
| 1 | `ai-gateway` repo live on staging with aliases, per-app keys, spend logs | 2, 3 |
| 2 | App on gateway: model factory, guard alias, embeddings, catalogue; Ollama mode kept | 1, 3 |
| 3 | `services/billing` with ledger, prices, reserve/settle, reconciler | 1, 2 |
| 4 | Accounts (OIDC) + Postgres/pgvector migration | 3, 5 |
| 5 | Web: PWA, sign-in, balance, top-up via merchant of record; hosted web beta on staging, then production | 6 |
| 6 | Expo app with feature parity, IAP via RevenueCat, TestFlight and Play internal testing, then store release | after 4 |
| 7 | Paystack for M-Pesa; optional US web-checkout link on iOS | after 5 |

Launch order: web beta first (fastest feedback on pricing), stores second.

## 15. Failure modes to watch

- **Streams cut mid-way:** settle on produced tokens; sweeper releases orphaned reserves.
- **Provider price changes:** nightly job compares provider prices to the `prices`
  table and alerts on any difference; no silent repricing.
- **Gateway outage:** aliases fall back to a second provider; if all fail, the app
  returns a clear error and releases reserves.
- **Store review:** rejection for payment links, missing deletion or missing Apple sign-in.
  Mitigated by IAP-only v1 and a pre-submission checklist.
- **Merchant of record declines Kenya:** fallbacks listed in section 9.
- **Single VPS failure:** snapshots plus off-site backups; recovery time target 4 hours,
  documented runbook.
- **Guard passes doubling cost:** measured by the guard eval; tuned per surface.

## 16. Calls made during the builder check

- **[call]** Prices listed in USD; the merchant of record and stores show local
  currency equivalents. Ledger stays in USD micro-dollars.
- **[call]** Premium models require purchased credits; the free grant cannot be spent on them.
- **[call]** Inactive accounts: after 12 months without sign-in, email notice, then
  delete study data 30 days later. Purchased balance stays on the account record.
- **[call]** Streamlit UI and multi-model analysis are not deployed in hosted mode.
- **[call]** Web search in Study Agent stays, charged only for the model tokens it uses.

## 17. Left to the builder

- OIDC provider pick (criteria in 7.2).
- Exact Hetzner instance type and region after load testing.
- Exact LiteLLM version and alias-to-provider mapping, from current provider prices.
- UI design of balance, top-up and price display, consistent with `DESIGN.md`.

## Sources

- Paddle supported countries: https://developer.paddle.com/concepts/sell/supported-countries-locales
- Paystack Kenya pricing: https://paystack.com/ke/pricing
- Paystack live in Kenya: https://paystack.com/blog/company-news/kenya
- Stripe in Kenya, conflicting reports: https://intasend.com/payments/is-stripe-available-in-kenya-best-alternative-in-kenya
- GLM-4.6 on OpenRouter: https://openrouter.ai/z-ai/glm-4.6
- Qwen3 vs GLM pricing comparison: https://openrouter.ai/compare/qwen/qwen3-235b-a22b-thinking-2507/z-ai/glm-4.6
- LiteLLM response headers: https://docs.litellm.ai/docs/proxy/response_headers
- LiteLLM spend tracking: https://docs.litellm.ai/docs/proxy/cost_tracking
- LiteLLM streaming cost header issue: https://forum.cursor.com/t/litellm-proxy-cost-per-request-tracker/158080
- Apple US external purchase links: https://www.macrumors.com/2025/05/01/apple-updates-u-s-app-review-guidelines-epic/
- Google Play expanded billing 2026: https://android-developers.googleblog.com/2026/06/play-expanded-billing.html
