#!/usr/bin/env bash
# Restart only the PreparationPalAI server and worker (after a code or migration change), by
# their recorded pids; gateway, databases, billing and sign-in keep running.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE="$ROOT/scripts/local_stack/.state"
for name in app worker; do
  if [ -f "$STATE/$name.pid" ]; then
    pid="$(cat "$STATE/$name.pid")"
    kill "$pid" 2>/dev/null
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    rm -f "$STATE/$name.pid"
  fi
done
exec "$ROOT/scripts/local_stack/start_app.sh"
