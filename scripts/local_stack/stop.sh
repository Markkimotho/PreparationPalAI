#!/usr/bin/env bash
# Stop the local stack started by start_app.sh and docker-compose.logto.yml. Stops only these processes and containers.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE="$ROOT/scripts/local_stack/.state"
for name in app worker billing; do
  [ -f "$STATE/$name.pid" ] && kill "$(cat "$STATE/$name.pid")" 2>/dev/null && rm -f "$STATE/$name.pid"
done
docker compose -f "$ROOT/tests/support/docker-compose.pg.yml" down >/dev/null 2>&1
(cd "$ROOT/services/billing" && docker compose -f docker-compose.test.yml down >/dev/null 2>&1)
(cd "$HOME/Projects/ai-gateway" && docker compose -f docker-compose.test.yml down >/dev/null 2>&1)
[ "${1:-}" = "--all" ] && docker compose -f "$ROOT/scripts/local_stack/docker-compose.logto.yml" down >/dev/null 2>&1
echo "stopped${1:+ (including sign-in)}"
