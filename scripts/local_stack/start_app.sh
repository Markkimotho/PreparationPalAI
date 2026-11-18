#!/usr/bin/env bash
# Start everything the phone app needs locally, except sign-in (docker-compose.logto.yml):
# the AI gateway with its fake model provider, billing on Postgres, and the Tayarishe
# server plus ingestion worker on http://localhost:18000 (what the simulator build calls).
# Local trial only: answers come from a fake provider, data lives in throwaway databases.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE="$ROOT/scripts/local_stack/.state"
mkdir -p "$STATE"
# A process already running from an earlier start is left alone (pid file + kill -0).
running() { [ -f "$STATE/$1.pid" ] && kill -0 "$(cat "$STATE/$1.pid")" 2>/dev/null; }
: "${OIDC_NATIVE_CLIENT_ID:?run setup_logto.py first; it prints the native client id}"

echo "gateway…"
(cd "$HOME/Projects/ai-gateway" && docker compose -f docker-compose.test.yml up -d --build >/dev/null)
until curl -sf http://127.0.0.1:14000/health/liveliness >/dev/null; do sleep 3; done
[ -s "$STATE/gwkey" ] || curl -s -X POST http://127.0.0.1:14000/key/generate -H 'Authorization: Bearer sk-test-master' \
  -H 'Content-Type: application/json' -d '{"key_alias":"app-local","models":["all-proxy-models"]}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])' > "$STATE/gwkey"

echo "databases…"
docker compose -f "$ROOT/tests/support/docker-compose.pg.yml" up -d >/dev/null
(cd "$ROOT/services/billing" && docker compose -f docker-compose.test.yml up -d >/dev/null)
until docker compose -f "$ROOT/tests/support/docker-compose.pg.yml" exec -T db pg_isready -U app >/dev/null 2>&1; do sleep 2; done
until (cd "$ROOT/services/billing" && docker compose -f docker-compose.test.yml exec -T db pg_isready -U billing >/dev/null 2>&1); do sleep 2; done
docker compose -f "$ROOT/tests/support/docker-compose.pg.yml" exec -T db psql -U app -d app -c "CREATE DATABASE local" >/dev/null 2>&1 || true
(cd "$ROOT/services/billing" && docker compose -f docker-compose.test.yml exec -T db psql -U billing -d billing -c "CREATE DATABASE local" >/dev/null 2>&1 || true)

echo "billing…"
(cd "$ROOT/services/billing"
 export BILLING_DATABASE_URL=postgresql://billing:test@127.0.0.1:15432/local BILLING_SERVICE_TOKEN=local-token BILLING_REQUIRE_VERIFIED_EMAIL=false
 .venv/bin/python -m billing.migrate >/dev/null
 running billing || { nohup .venv/bin/python -m uvicorn billing.api:app --port 18100 > "$STATE/billing.log" 2>&1 & echo $! > "$STATE/billing.pid"; })

echo "server and worker…"
export INFERENCE_BACKEND=gateway GATEWAY_BASE_URL=http://127.0.0.1:14000 GATEWAY_API_KEY="$(cat "$STATE/gwkey")" OLLAMA_MODEL=open-default
export EMBEDDING_DIMENSIONS=1024 BILLING_ENABLED=true BILLING_BASE_URL=http://127.0.0.1:18100 BILLING_SERVICE_TOKEN=local-token
export BILLING_OUTBOX_DB="$STATE/outbox.sqlite3" STORAGE_BACKEND=postgres DATABASE_URL=postgresql://app:test@127.0.0.1:15433/local
export AUTH_MODE=oidc OIDC_ISSUER=https://localhost:8443/oidc OIDC_JWKS_URL=http://localhost:3001/oidc/jwks
export OIDC_AUDIENCE=https://api.tayarishe.local OIDC_NATIVE_CLIENT_ID OIDC_WEB_CLIENT_ID="${OIDC_WEB_CLIENT_ID:-ppal-web-local}" JOBS_DIR="$STATE/jobs" EMBEDDED_WORKER=false
cd "$ROOT"
.venv/bin/python -m app.migrate_db >/dev/null
running app || { nohup .venv/bin/python -m uvicorn app.api:app --port 18000 > "$STATE/app.log" 2>&1 & echo $! > "$STATE/app.pid"; }
running worker || { nohup .venv/bin/python -m app.jobs > "$STATE/worker.log" 2>&1 & echo $! > "$STATE/worker.pid"; }
until curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18000/api/health | grep -qE '^(200|401)$'; do sleep 2; done   # 401: up, sign-in required
echo "ready: http://localhost:18000 (logs in $STATE)"
