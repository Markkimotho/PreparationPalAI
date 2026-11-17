# Plan 1: AI gateway and gateway-backed inference

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Mark's shared LiteLLM gateway as its own repo and move every PreparationPalAI model call (chat, structured output, moderation, vision, embeddings, catalogue) onto it behind `INFERENCE_BACKEND=gateway`, recording token usage for every call, while `INFERENCE_BACKEND=ollama` keeps self-hosting unchanged.

**Architecture:** `ai-gateway` is a separate repo (LiteLLM proxy + its own Postgres, Compose). In this repo one factory in `app/llm.py` builds either the existing Ollama model or an OpenAI-compatible model pointed at the gateway; both share the guard logic. A context-scoped meter (`app/metering.py`) collects a `UsageRecord` per model call, which Plan 2 turns into charges.

**Tech Stack:** Python 3.11, FastAPI, LangChain (`langchain-openai` added, `langchain-ollama` kept), LiteLLM proxy (pinned image), Postgres 16, Docker Compose, pytest.

**Spec:** `specs/2026-11-17-hosted-product-design.md` (sections 6, 7.1, 7.4, 13)

**Plan series:** 1 gateway + inference (this) · 2 billing service · 3 accounts + Postgres/pgvector · 4 web PWA + payments · 5 Expo app + IAP · 6 Paystack. Plans 1 and 2 run in parallel; 3-6 are written once 1-2 land.

## Global Constraints

- `INFERENCE_BACKEND` is `ollama` (default) or `gateway`. With `ollama`, every existing test passes unchanged.
- Gateway aliases, exact names: `open-default`, `open-fast`, `open-reasoning`, `guard`, `vision-open`, `embed-default`, `premium-claude`, `premium-gpt`, `premium-grok`.
- Moderation and verification always run on the `guard` alias in gateway mode, never on the user's model.
- Every gateway call passes `user=<workspace id>` (LiteLLM stores it as `end_user`) and `metadata={"spend_logs_metadata": {"action": ..., "request_id": ...}}`. Plain `metadata.request_id` is not retained by LiteLLM (verified in `ai-gateway` e2e).
- Provider keys only via `os.environ/...` references in LiteLLM config; no secret in either repo. `.env` stays gitignored.
- LiteLLM image pinned to an exact release tag (no `latest`, no `main-stable`).
- Gateway reachable only on the private Docker network `ai-gateway`; never published on a public port.
- Commit messages carry no Claude co-author line (Mark's rule).

## Review Focus

1. Provider returns 200 without `usage` → usage recorded with `estimated=True` (chars/4), never silently zero. Test in Task 3.
2. Gateway down, 5xx, or timeout → learner sees "The model service is unavailable. Please retry." and no `UsageRecord` is recorded. Test in Task 3.
3. Stale model preference (e.g. `qwen2.5:7b` saved in the browser) sent to a gateway deployment → 409 naming available models, not 500. Test in Task 6.
4. Switching backend on an existing Chroma directory (768-dim Ollama vectors vs gateway embeddings) → separate collection per embedding model, no dimension crash. Test in Task 5.
5. Model returns invalid JSON for a schema-constrained request → existing retry in `app/generation.py` still triggers in gateway mode. Test in Task 3.

---

### Task 1: `ai-gateway` repo with aliases, fallbacks and config gate tests

**Files (new repo `~/Projects/ai-gateway`):**
- Create: `config.yaml`, `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`, `scripts/new_app_key.sh`, `tests/test_config.py`, `pyproject.toml`

**Interfaces:**
- Produces: OpenAI-compatible API at `http://litellm:4000` on Docker network `ai-gateway`; aliases above; per-app virtual keys created by `scripts/new_app_key.sh <app> <monthly_budget_usd>`.

- [ ] **Step 1: Write failing tests** in `tests/test_config.py`:
  - `test_required_aliases_present`: set of `model_name` in `config.yaml` ⊇ the nine aliases.
  - `test_every_chat_alias_has_fallback`: each alias except `embed-default` and `guard` appears as a key in `router_settings.fallbacks`.
  - `test_no_inline_secrets`: every `api_key` value starts with `os.environ/`; `master_key` and `database_url` under `general_settings` likewise.
  - `test_image_is_pinned`: `docker-compose.yml` litellm image matches `r"ghcr\.io/berriai/litellm(-database)?:v\d+\.\d+\.\d+"`.
  - `test_gateway_not_published`: litellm service has no `ports`; it joins network `ai-gateway`.
- [ ] **Step 2: Run** `pytest tests -q` → FAIL (files missing).
- [ ] **Step 3: Write `config.yaml`** mapping aliases to providers (primary, then fallback): `open-default` → Z.ai GLM-4.6, fallback OpenRouter `z-ai/glm-4.6`; `open-fast` → OpenRouter Qwen3-14B class; `open-reasoning` → OpenRouter Qwen3-235B-A22B; `guard` → same model as `open-fast`; `vision-open` → GLM-4.6V; `embed-default` → Qwen3 embedding (pick current cheapest on OpenRouter or Alibaba Model Studio, record dimension in README); premium aliases → Anthropic, OpenAI, xAI current flagship. `general_settings`: `master_key`, `database_url`, `store_model_in_db: false`. Write `docker-compose.yml` (litellm pinned to the newest stable tag at execution time, Postgres 16 with volume, healthchecks, `mem_limit`), external network `ai-gateway`.
- [ ] **Step 4: Write `scripts/new_app_key.sh`** calling `POST /key/generate` with `key_alias`, `max_budget`, `budget_duration: "30d"`, `models` = all aliases; prints the key once.
- [ ] **Step 5: Run** `pytest tests -q` → PASS.
- [x] **Step 6: Commit.** DONE: private repo `Markkimotho/ai-gateway` created (Mark approved), image pinned to `v1.108.9`.

### Task 2: Gateway end-to-end test against a fake provider (DONE, 8 e2e + 12 gate tests green)

Findings folded in: keys need fallback aliases (script reads `/v1/models`); spend rows key on the provider response id (fake must return unique ids); read spend via `GET /spend/logs/v2` with `end_user` and dates; correlation via `spend_logs_metadata`.

**Files (ai-gateway):**
- Create: `tests/fake_provider/app.py`, `tests/fake_provider/Dockerfile`, `config.test.yaml`, `docker-compose.test.yml`, `tests/test_e2e.py`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `make e2e` (or `docker compose -f docker-compose.test.yml up --abort-on-container-exit`) used by CI.

- [ ] **Step 1: Write the fake provider**: OpenAI-compatible `/v1/chat/completions` (returns fixed JSON content and `usage {prompt_tokens: 11, completion_tokens: 7}`; stream mode emits chunks and a final usage chunk), `/v1/embeddings` (fixed 8-dim vectors). `/v1/chat/completions` returns 500 when model name is `broken`.
- [ ] **Step 2: Write tests** in `tests/test_e2e.py` (marker `integration`):
  - `test_chat_returns_usage`: `usage.prompt_tokens == 11`, `completion_tokens == 7`.
  - `test_stream_includes_usage` with `stream_options={"include_usage": True}`: last chunk has `usage.completion_tokens == 7`.
  - `test_fallback_on_provider_error`: alias `open-default` whose primary is `broken` returns 200.
  - `test_unknown_alias_rejected`: model `qwen2.5:7b` → 400.
  - `test_spend_logged_per_key`: after one call with a generated key and `user="ws1"`, `GET /spend/logs?api_key=...` has a row with `user == "ws1"` and metadata `request_id`.
  - `test_embeddings_alias`: `embed-default` returns 8-dim vectors.
- [ ] **Step 3: Run** e2e → FAIL until `config.test.yaml` points all aliases at the fake (with `broken` primary for `open-default`).
- [ ] **Step 4: Run** e2e → PASS. Add CI job running Task 1 tests and e2e.
- [ ] **Step 5: Commit.**

### Task 3: Usage meter and gateway chat model

**Files:**
- Create: `app/metering.py`, `tests/support/fake_openai.py`, `tests/test_metering.py`, `tests/test_gateway_llm.py`
- Modify: `app/config.py` (settings), `app/llm.py`, `requirements.txt` + `pyproject.toml` (add `langchain-openai`), `.env.example`

**Interfaces:**
- Produces (`app/metering.py`):
  - `@dataclass(frozen=True) UsageRecord(alias: str, purpose: Literal["main","guard","vision","embed"], input_tokens: int, output_tokens: int, estimated: bool)`
  - `class Meter: records: list[UsageRecord]; def add(self, r: UsageRecord) -> None` (add calls an optional `on_add: Callable[[UsageRecord], None]` hook; Plan 2 uses it to stop a request that exceeds its reservation)
  - `@contextmanager metering_scope(action: str, request_id: str, on_add=None) -> Iterator[Meter]`
  - `def record(r: UsageRecord) -> None` (no-op outside a scope), `def current_meter() -> Meter | None`, `def current_action() -> tuple[str, str] | None`
- Produces (`app/config.py`): `inference_backend: Literal["ollama","gateway"] = "ollama"`, `gateway_base_url: str = ""`, `gateway_api_key: SecretStr = SecretStr("")`, `guard_alias: str = "guard"`, `vision_alias: str = "vision-open"`, `embedding_alias: str = "embed-default"`; validator: gateway mode requires both URL and key; in gateway mode `ollama_model` default is replaced by `open-default`.
- Produces (`app/llm.py`): `def chat_model(model: str, *, temperature: float = 0, format: dict | None = None, num_predict: int | None = None, num_ctx: int | None = None, purpose: str = "main", **_ignored) -> BaseChatModel` returning guarded Ollama or guarded gateway model; `def raw_chat_model(...)` same signature without guards (used by the safety judge only). `ChatOllama = chat_model` alias kept for one task so call sites migrate in Task 4.
- Produces: `class ModelServiceUnavailable(RuntimeError)` with message `"The model service is unavailable. Please retry."`, mapped to HTTP 503 and to the SSE error frame.

- [ ] **Step 1: Write `tests/test_metering.py`**:
  - `test_record_outside_scope_is_noop`
  - `test_scope_collects_records_in_order`
  - `test_scope_survives_threadpool`: record inside `anyio.to_thread.run_sync` within the scope lands in the meter.
  - `test_nested_scope_rejected`: entering a scope inside a scope raises `RuntimeError`.
  - `test_on_add_hook_can_abort`: hook raising propagates out of `record`.
- [ ] **Step 2: Write `tests/support/fake_openai.py`** (in-process server like `fake_ollama.py`) with switches: `usage=None`, `status=500`, `content="not json"` once, records received request bodies.
- [ ] **Step 3: Write `tests/test_gateway_llm.py`**:
  - `test_schema_maps_to_response_format`: `chat_model("open-default", format=schema).invoke(...)` sends `response_format.type == "json_schema"` and the schema.
  - `test_num_predict_maps_to_max_tokens`: sends `max_tokens == min(num_predict, llm_output_tokens)`.
  - `test_sends_user_and_metadata`: body has `user == workspace id` and `metadata.spend_logs_metadata == {"action": ..., "request_id": ...}`.
  - `test_records_main_and_guard_usage`: one invoke records one `main` (alias `open-default`) and the guard records (alias `guard`, purpose `guard`) with fake token counts.
  - `test_missing_usage_is_estimated`: `usage=None` → record `estimated is True` and `input_tokens == ceil(chars/4)`.
  - `test_gateway_error_raises_unavailable_and_records_nothing` (Review Focus 2).
  - `test_invalid_json_triggers_generation_retry` (Review Focus 5): through `app/generation.py`, first reply `"not json"`, second valid → result valid, two `main` records.
  - `test_ollama_backend_unchanged`: with default settings `chat_model` returns `GuardedChatOllama`.
- [ ] **Step 4: Run** → FAIL.
- [ ] **Step 5: Implement.** Extract guard behaviour from `GuardedChatOllama` into a mixin `_Guarded` used by both `GuardedChatOllama` and new `GuardedChatGateway(ChatOpenAI)`. Gateway model: `base_url=f"{gateway_base_url}/v1"`, `api_key`, `stream_usage=True`, `timeout=httpx.Timeout(llm_timeout, connect=5)`, `extra_body={"user": ..., "metadata": ...}`. Read `usage_metadata` after each generation and call `record(...)`. Convert `httpx`/`openai` connection, timeout and 5xx errors into `ModelServiceUnavailable`. Register an exception handler in `app/api.py` (503) and handle it in `_sse`.
- [ ] **Step 6: Run** `pytest tests/test_metering.py tests/test_gateway_llm.py -q` → PASS; `pytest tests -q` → all PASS.
- [ ] **Step 7: Commit.**

### Task 4: Safety judge, vision and all call sites on the factory

**Files:**
- Modify: `app/safety.py:42-68`, `app/drawings.py:170-178,220-245`, `app/chain.py`, `app/graph.py`, `app/code_assistant.py`, `app/quiz.py`, `app/flashcards.py`, `app/coach.py`, `app/analysis.py`, `app/exports.py`
- Create: `tests/test_inference_boundary.py`
- Modify: `tests/test_drawings.py`, `tests/test_study_guardrails.py` (add gateway-mode cases)

**Interfaces:**
- Consumes: `chat_model`, `raw_chat_model`, `record`, settings from Task 3.
- Produces: `def vision_json(model: str, system: str, text: str, image_png: bytes, schema: dict) -> dict` in `app/llm.py` (Ollama `/api/chat` with `images` or gateway chat with a `data:image/png;base64,...` `image_url` part; records purpose `vision`); `def supports_vision(model: str) -> bool` in `app/model_catalog.py` (Ollama `/api/show` capabilities, or gateway `/model/info` `supports_vision`).

- [ ] **Step 1: Write `tests/test_inference_boundary.py`**: `test_only_llm_module_imports_ollama_chat`: scanning `app/*.py`, only `app/llm.py` and `app/embeddings.py` import `langchain_ollama`, and only `app/llm.py`, `app/analysis.py`, `app/diagnostics.py`, `app/api.py`, `app/model_catalog.py` reference `ollama_base_url`.
- [ ] **Step 2: Add gateway-mode tests**: `test_judge_uses_guard_alias_in_gateway_mode` (request model == `guard` though caller passed `open-reasoning`); `test_vision_review_gateway_sends_image_url`; `test_vision_review_rejects_non_vision_alias` (409 text unchanged).
- [ ] **Step 3: Run** → FAIL.
- [ ] **Step 4: Implement.** `judge()` builds its classifier with `raw_chat_model(guard alias in gateway mode else model, format=..., num_predict=40, purpose="guard")`. `drawings.vision_call` → `vision_json`; capability check → `supports_vision`. Replace every `ChatOllama(...)` call with `chat_model(...)` and drop `base_url=` arguments; remove the temporary alias.
- [ ] **Step 5: Run** `pytest tests -q` → all PASS.
- [ ] **Step 6: Commit.**

### Task 5: Embeddings through the gateway, collection per embedding model

**Files:**
- Modify: `app/embeddings.py`, `app/vectorstore.py:17-38`
- Test: `tests/test_workspace_vectors.py` (add cases), `tests/test_embeddings_backend.py` (new)

**Interfaces:**
- Produces: `def get_embeddings() -> Embeddings` (Ollama or `OpenAIEmbeddings(model=embedding_alias, base_url=gateway/v1, check_embedding_ctx_length=False)` wrapped so each `embed_documents`/`embed_query` call records purpose `embed` with input tokens from the response, estimated if absent); `def collection_name() -> str` = `f"{chroma_collection_name}--{slug(embedding model or alias)}"`.

- [ ] **Step 1: Tests**: `test_gateway_embeddings_record_usage`; `test_collection_name_differs_per_embedding_model`; `test_switching_backend_does_not_mix_dimensions` (Review Focus 4: write with fake 8-dim gateway vectors into a dir that already holds a 768-dim Ollama collection, query succeeds).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** Existing self-hosted data keeps working: when backend is `ollama` and the legacy collection name exists, use it (test `test_legacy_ollama_collection_still_read`).
- [ ] **Step 4: Run** `pytest tests -q` → PASS. **Step 5: Commit.**

### Task 6: Catalogue, health and model management in gateway mode

**Files:**
- Modify: `app/analysis.py:48-60`, `app/model_catalog.py`, `app/api.py:208-265`, `app/diagnostics.py:95-110`, `frontend/src/components/` model picker (hide Pull when `pullable` is false)
- Test: `tests/test_model_catalog.py`, `tests/test_model_pull.py`, `tests/test_diagnostics.py`, frontend Vitest for picker

**Interfaces:**
- Produces: `get_installed_models()` returns gateway `/v1/models` ids (30 s cache) in gateway mode; catalogue entries gain `tier: Literal["open","premium"] | None` and `pullable: bool`; `/api/models` response adds `pullable` per entry. Pull routes return 404 `"Model downloads are managed by the hosting provider."` in gateway mode.

- [ ] **Step 1: Tests**: `test_gateway_catalogue_lists_aliases_with_tiers` (premium-* → `premium`, open-* → `open`, `guard`/`embed-default` hidden); `test_stale_model_preference_returns_409` (Review Focus 3: `qwen2.5:7b` → 409 whose detail lists `open-default`); `test_pull_disabled_in_gateway_mode`; `test_readiness_checks_gateway` (`/health/liveliness` down → not ready); picker test: no Pull button when `pullable` false.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** backend and `cd frontend && npm test` → PASS. **Step 5: Commit.**

### Task 7: Hosted compose wiring, live smoke and evals on gateway aliases

**Files:**
- Create: `docker-compose.hosted.yml`, `scripts/smoke_gateway.py`, `engineering/runbooks/gateway.md`
- Modify: `.env.example`, `engineering/architecture.md` (inference section), `mkdocs-contributors.yml` nav, `evals/conftest.py` (run on `INFERENCE_BACKEND=gateway` with `EVAL_MODELS=open-default,open-fast,open-reasoning`)

- [ ] **Step 1:** `docker-compose.hosted.yml` overrides `web`/`worker`: `INFERENCE_BACKEND=gateway`, `GATEWAY_BASE_URL=http://litellm:4000`, `GATEWAY_API_KEY=${GATEWAY_API_KEY:?}`, joins external network `ai-gateway`, removes the `ollama` dependency.
- [ ] **Step 2:** `scripts/smoke_gateway.py`: one chat, one schema quiz, one embedding, one moderation through the running app; prints recorded usage per call; exits non-zero on any failure. Gate-test its argument parsing only.
- [ ] **Step 3:** With staging gateway and real provider keys, run `python scripts/smoke_gateway.py` → all OK; run `pytest evals -m eval` per alias → write report under `evals/reports/`; the default alias must meet existing thresholds.
- [ ] **Step 4:** Runbook: create a key, rotate provider keys, change alias mapping, read spend logs. Build contributor docs strictly (`mkdocs build -f mkdocs-contributors.yml --strict`) → PASS.
- [ ] **Step 5: Commit and push.**
