# Hosted end-to-end scenario

Runs two verified learners and one unverified learner through the real app, billing service, LiteLLM
gateway (with a fake model provider), Postgres/pgvector and the ingestion worker, then deletes an account.
It found three real bugs (chat call allowance, dropped embedding `dimensions`, Decimal in the reconcile
report). Re-run it after changes to auth, storage, billing or the gateway config.

1. Gateway: `cd ~/Projects/ai-gateway && docker compose -f docker-compose.test.yml up -d --build`, then
   create a key (`POST /key/generate`, `key_alias: app-integration`, `models: ["all-proxy-models"]`).
2. Databases: `docker compose -f tests/support/docker-compose.pg.yml up -d` and
   `cd services/billing && docker compose -f docker-compose.test.yml up -d`; create a database `e2e` in each.
3. Issuer: `python scripts/e2e_hosted/issuer.py issuer.json` (serves JWKS, writes tokens for alice, bob, mallory).
4. Billing: `python -m billing.migrate` then `uvicorn billing.api:app --port 18100` (`BILLING_SERVICE_TOKEN=e2e-token`).
5. App: set `INFERENCE_BACKEND=gateway`, `EMBEDDING_DIMENSIONS=1024`, `BILLING_ENABLED=true`, `STORAGE_BACKEND=postgres`,
   `AUTH_MODE=oidc` (issuer, audience and JWKS from `issuer.json`), `OLLAMA_MODEL=open-default`,
   `EMBEDDED_WORKER=false`; run `python -m app.migrate_db`, `uvicorn app.api:app --port 18000` and `python -m app.jobs`.
6. `python scripts/e2e_hosted/scenario.py <folder containing issuer.json>`.
7. Reconcile: `python -m billing.jobs reconcile` (set `GATEWAY_*`). Reset the gateway as well as the billing
   database between runs, or old gateway usage will show up as drift.

Expected: alice gets 500 starter credits and a document in her own workspace; mallory (unverified email) gets
402; bob sees none of alice's data; deleting bob returns 204 and later requests return 403; alice is untouched.

## Payment scenario

`payments.py` drives a purchase and refund through the real app and billing service, with
`fake_paddle.py` standing in for Paddle's transactions API (start billing with
`PADDLE_API_BASE=http://127.0.0.1:18200` and test `PADDLE_*` values) and correctly signed webhooks.

    python scripts/e2e_hosted/fake_paddle.py 18200 paddle.jsonl
    python scripts/e2e_hosted/payments.py issuer.json paddle.jsonl <PADDLE_WEBHOOK_SECRET>

Expected: the checkout is tagged with the signed-in learner even when the client names another account;
five deliveries of the same payment credit once; a forged signature gets 401; a half refund delivered twice
is applied once; the history shows the purchase and the refund.
