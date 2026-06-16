# Bounded local inference

Runtime inference and embeddings use Ollama only. Optional cloud dependencies in
the package metadata do not activate a cloud fallback. Configure `OLLAMA_BASE_URL`,
`OLLAMA_MODEL`, and `OLLAMA_EMBEDDING_MODEL` on the server. URLs with embedded
credentials and empty model names fail configuration validation. Keep secrets in
server environment files outside version control; no provider settings contain
client secrets or are compiled into the SPA.

Every chat model constructor uses the shared bounded factory. `LLM_TIMEOUT` (180
seconds by default) bounds HTTP inactivity; connection timeout is five seconds.
`LLM_CONTEXT_TOKENS` (8192) bounds the model context and `LLM_OUTPUT_TOKENS` (2048)
bounds completion generation. Long derivations may need an explicit increase up
to the configured validation ceilings. These are HTTP-inactivity and token limits,
not a guarantee of total wall time on slow hardware. `REQUEST_MAX_BYTES` (2 MB)
bounds JSON request bodies, including chunked requests. Uploads have separate limits.

`REQUESTS_PER_MINUTE` (30) and `REQUESTS_PER_DAY` (1000) apply to POST API requests,
per authenticated key and workspace. Budgets persist in `USAGE_DB`
(`data/usage/usage.sqlite3`) and use SQLite transactions across API processes.
Rejected requests return 429 and Retry-After. Failed accepted requests still consume
budget, preventing repeated failures from becoming an unbounded retry loop. Missing
models return actionable 409 errors before inference. Readiness checks separately
report unavailable model and embedding dependencies.

Use separate keys per person, even in a shared workspace, for individual budgets.
Changing/revoking a key creates a new budget identity. Restrict access to model pulls
to administrators; model downloads use the existing bounded 900-second HTTP timeout.
