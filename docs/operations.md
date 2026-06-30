# Operational triage

`/health/live` checks the API process without calling providers. `/health/ready`
returns 503 until Ollama, the configured chat and embedding models, and vector
storage are available. Its response contains dependency booleans, never model
contents or prompts. Probes are public; `/metrics` requires an admin bearer key
when authentication is enabled. Supply that credential through a read-only secret
file and Prometheus `authorization.credentials_file`, never the config repository.

Every HTTP/SSE response has a server-generated `X-Request-ID`. JSON request logs
include route templates, workspace, outcome, elapsed time, and request ID. The
formatter allowlists fields and emits only exception types, not exception messages,
tracebacks, source URLs, filenames or study content. Uvicorn access logs are disabled
to avoid logging query strings. Operational messages outside the allowlist become
`application_event`. Do not enable debug HTTP logging in production. Browser error
reports send only an allowlisted category, capped at five per tab; stacks, messages
and URLs stay on the device.

Use request IDs to correlate failed responses with the `app.requests` event and
workspace. Inspect readiness first for outages. For slow generation, inspect
inference histograms, output/context caps and available RAM; try a smaller model.
For retrieval failures, inspect the retrieval counter, storage permissions and
embedding-model readiness. Never paste learner documents into incident tickets.

The monitoring overlay loads provider outage, server-error and p95 latency rules.
Prometheus evaluates them locally; configure an operator-owned Alertmanager to
deliver notifications. Existing Grafana dashboards show HTTP/inference latency,
errors, token events and KB size. New HTTP counters include workspace correlation;
request IDs belong in logs rather than metric labels to avoid unbounded cardinality.
Queue status and worker health are added with the ingestion worker.
