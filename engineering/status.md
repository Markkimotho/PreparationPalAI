# Issue implementation progress

Development status, not a promise of validated learning outcomes. The
[user guide](https://markkimotho.github.io/PreparationPalAI/) describes how to use the product.

Work is on `feat/preparation-coach`, tracked by draft PR #11. Each row describes
implemented behavior and the remaining verification needed before closing issues.

| Issue | Implemented | Remaining verification / operator action |
| --- | --- | --- |
| #1 Workspace access | Bearer digest configuration, roles, scoped vector clients/storage/checkpoints/history, memory-only browser sign-in, cross-workspace and permission tests | Configure real workspace keys and HTTPS for deployment |
| #2 Inference safety | Validated provider settings, request/body/context/output/time limits, durable per-key budgets, actionable missing-model errors | Tune limits for the deployment hardware |
| #3 Ingestion safety | DNS-pinned public fetching, redirect/type/size limits, signature checks, isolated/time-bounded extraction, scanner hook, idempotent writes and resumable jobs | Install/configure a scanner if required; exercise real scanned documents |
| #4 Quality gates | Versioned science dataset, offline CI/nightly reports, isolated live retrieval/citation/evidence/quiz/card benchmark and thresholds, provider/model digests | Install models and run the live gate; provision trusted `ollama` runner and branch protection |
| #5 Diagnostics | Request/workspace correlation, content-free structured logs, liveness/readiness, queue/dependency/frontend metrics, Grafana queue panels and alerts | Configure authenticated Prometheus scrape and notification delivery in production |
| #6 Deployment | Non-root API/worker, bounded containers, persistent queue leases, volumes, TLS/CORS/SSE topology, hash-verified backup/restore; GitHub container PDF/queue/embedding/SSE/frontend smoke passed with a protocol stub | Run the deployment exercise with real models and the production domain; migrate ownership of any existing root-owned volumes |
| #7 Preparation coach | Saved modes/results, timed mixed exams, scientific grading breakdown, interview follow-ups, adaptive recap, weak-area review, equation rendering | Validate question/feedback quality with real GLM/DeepSeek and representative syllabi |
| #8 Model support | Configurable GLM/DeepSeek catalogue, dynamic installed models, availability states, streamed pull progress, per-surface preferences, exact propagation tests | Real model download/inference validation |
| #9 Mobile/accessibility | Responsive routes, 44px controls, focus restoration, native keyboard behavior, visible correctness labels, reduced motion, active study tests; latest seven-route browser check passed at all four widths after storage recovered | Human screen-reader and physical mobile keyboard checks |
| #10 Public SEO | Complete server HTML, canonical/social/schema metadata, sitemap/robots, noindex workspace, real 404 handling, configured origin checks | Public-domain/social-preview verification after deployment |

No issues are automatically closed while the remaining live/deployment checks are
unverified. See security, inference, ingestion, quality, operations and deployment
documents in [runbooks](runbooks/security.md) for setup and reproduction commands.
