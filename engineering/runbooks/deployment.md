# Deployment and recovery

For maintainers operating a shared installation. For a personal installation,
see [get the app](https://markkimotho.github.io/PreparationPalAI/start/access/).

The local Compose topology is Ollama + a one-shot model initializer + the non-root
FastAPI/SPA container + a separate ingestion worker. API and worker share the jobs
and Chroma volumes. Coach, flashcards and usage budgets have independent persistent
volumes. Model downloads remain in `ollama_models`. Queue files are retained for
retry/recovery; define an operator retention policy before long-running use.

The API and worker run as UID 10001, with read-only root filesystems, a bounded
temporary filesystem, dropped Linux capabilities, no-new-privileges, PID/memory/CPU
limits and a 180-second shutdown grace period. New volume directories have the
correct UID in the image. Existing volumes created by older root images require an
operator-owned ownership migration before rollout; back them up first. Ollama is
bounded at 10 GiB/4 CPUs by default; adapt this to the selected model and host RAM.

Development binds API/Ollama ports to loopback. Production uses:

```
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

Set `PUBLIC_HOST`, `PUBLIC_BASE_URL`, and server-side `AUTH_TOKENS` digests first.
The production overlay enforces authentication and puts Caddy on ports 80/443 for
automatic TLS. Ensure DNS points to the host and those ports are reachable. Caddy
disables response buffering for SSE and allows long reads. No WebSocket endpoints
currently exist. Production `CORS_ORIGINS` defaults to `[]` because the SPA/API share
an origin; configure exact origins only if serving them separately. HTTPS/security
headers belong at the reverse proxy. Do not publish the legacy Streamlit UI.

`/health/live` is the container liveness probe. `/health/ready` verifies model,
embedding, vector-storage, and worker readiness. Model downloads can take minutes:
keep traffic out until readiness succeeds. Workers maintain SQLite heartbeat/lease
records; interrupted jobs are reclaimed after the lease expires, with at most three
attempts before manual retry. The local non-Docker API starts an embedded worker by
default; set `EMBEDDED_WORKER=false` when running `python -m app.jobs` separately.
The old synchronous ingestion routes are disabled in production.

Schema migration policy: queue tables are created if absent; the run-token column
is added idempotently for older queues. Back up before deploying schema changes.
Use one ingestion worker per host by default. SQLite-backed embedded Chroma is not
a horizontally distributed storage service; migrate to managed/shared storage
before spanning hosts.

## Backups

Stop API and worker writes before taking a snapshot. Mount all six data volumes
(Chroma, flashcards, coach, jobs, usage and optional uploaded PDFs) under their
normal `/app/data` paths in a one-shot container, and mount a writable backup
directory outside `/app/data`. Run:

```
python -m scripts.backup backup --data-dir /app/data --archive /backups/preppal.tar.gz --quiesced
python -m scripts.backup verify --archive /backups/preppal.tar.gz
```

The manifest hashes every file. Archive creation verifies its own manifest before
publication. Store archives on encrypted off-host storage, restrict access and
expire old copies; they contain private study material. Back up Ollama models
separately or re-pull exact tags/digests. Keep auth configuration in the operator's
secret store, not in the data archive. A copied live SQLite/Chroma volume is not a
consistent backup; quiescing both writers is required.

Restore only into a new empty data tree:

```
python -m scripts.backup restore --archive /backups/preppal.tar.gz --data-dir /recovery/data
```

Restore validates all hashes and rejects traversal, duplicate entries and links
before writing. Existing data is never overwritten. Attach restored directories or
copy them into new named volumes with UID 10001 ownership, keep the old volumes for
rollback, start Ollama/worker/API, then check readiness and the deployment smoke
script. Restart interrupted jobs only after verifying workspace keys and access.
Round-trip and unsafe-archive tests run in CI.

Run `python -m scripts.deployment_smoke` for read-only readiness/frontend/API probes,
with `SMOKE_BASE_URL` and `SMOKE_ACCESS_KEY` in the environment. Pass `--exercise`
only against a disposable workspace: it deliberately adds public study material,
waits for ingestion, and checks streamed chat tokens/completion. This requires real
installed models and external search connectivity; the deterministic browser smoke
script uses mocked dependencies and is separate from the deployment exercise.
