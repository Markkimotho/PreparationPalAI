---
description: Sign-in with Logto, hosted storage on Postgres, free allowance rules, and account deletion.
---
# Accounts, storage and deletion

Hosted deployments (`docker-compose.hosted.yml`) let learners sign in with email, Google or Apple
through a self-hosted [Logto](https://logto.io). The app only verifies tokens; it never sees passwords.
Self-hosted installations keep static workspace keys (`AUTH_MODE=tokens`) and local files.

## How a request is authenticated

1. The learner signs in at `AUTH_HOST` and the client receives an access token for your API
   (`OIDC_AUDIENCE`).
2. Each `/api` request carries `Authorization: Bearer <token>`. `app/oidc.py` accepts only RS256 or ES256
   tokens with the right issuer and audience, an expiry and a subject (60 seconds of clock leeway).
3. The token's subject becomes a private workspace id, `u-` plus 20 hex characters of a one-way hash.
   Email addresses are never used as ids or paths. Every store filters by that workspace.
4. Signing keys are fetched privately from `OIDC_JWKS_URL`. An unknown key id triggers at most one
   refetch every 30 seconds; if Logto is unreachable, cached keys keep working for up to 24 hours and
   then tokens are refused rather than trusted blindly.
5. Roles come from a `roles` claim (`admin`, `editor`, `reader`); no claim means `editor`.

## One-time Logto setup

Reach the admin console through an SSH tunnel (it is bound to loopback only):
`ssh -L 3002:127.0.0.1:3002 your-server`, then open `http://localhost:3002`.

1. **API resource**: create one whose identifier is your `OIDC_AUDIENCE` (for example `https://api.example.com`).
2. **Web application**: a traditional or SPA app with your `PUBLIC_HOST` redirect URIs.
3. **Native application** for the Expo app: add its redirect URI and enable the API resource.
4. **Sign-in experience**: email one-time code, plus Google and Apple. Apple sign-in is required on iOS
   whenever another social sign-in is offered.
5. **Verified email**: keep "require verified email" on. The free allowance is only granted for verified emails.
6. **Management API** (optional, for deleting the sign-in): create a machine-to-machine application with
   the Logto Management API role and set `LOGTO_MANAGEMENT_APP_ID` and `LOGTO_MANAGEMENT_APP_SECRET`.
7. **Roles** (optional): create `admin`, `editor`, `reader` roles and add a `roles` claim to the access token.

## Free starter allowance

500 credits on open models, once per person. Billing grants it only when the token says the email is
verified, the address is not on the disposable-domain list (`services/billing/billing/disposable_domains.txt`),
and no other account already claimed the same mailbox. Case, `+tag` and (at Gmail) dots are ignored when
comparing mailboxes. A refused attempt neither uses the daily cap nor blocks the address. Only a one-way
key of the mailbox is stored.

## Storage

`STORAGE_BACKEND=postgres` keeps flashcards, coach sessions, drawings, ingestion jobs, rate-limit counters
and document chunks (pgvector) in the `app` schema. Every table has a non-null `workspace` column and an
index that starts with it; a test fails the build for any table that does not. `python -m app.migrate_db`
applies migrations and runs on every start of `web` and `worker`.

Embeddings are stored as `vector(1024)`. The gateway's `embed-default` returns 4096 dimensions unless asked,
so set `EMBEDDING_DIMENSIONS=1024` before the first upload and check that your provider honours it. A wrong
size is refused with a clear error and nothing is stored.

## Deleting an account

`DELETE /api/account` (signed-in learners only) does, in order:

1. closes the billing account (open holds are released, new reservations are refused, the anonymous ledger is kept);
2. removes every stored item for the workspace from every store;
3. deletes the Logto user, when management credentials are configured.

It is safe to repeat. If billing is down nothing is deleted and the learner retries. If a store fails the
response says some data remains and a retry finishes it. If only the Logto step fails, the data is already
gone and a retry removes the sign-in. Purchased credits that remain are forfeited, so show the balance and
warn before asking for confirmation. The one-way mailbox key is kept so deleting and re-registering cannot
claim a second free allowance.

New tables must register a deleter in `app/purge.py`; `tests/test_account_deletion_pg.py` fails otherwise.

## Backups and recovery

Back up the `app-db`, `billing-db` and `logto-db` volumes together (they reference each other by account
id). Restore all three from the same point in time.
