"""FastAPI backend for the PreparationPalAI React frontend.

This is a thin adapter: every route delegates to an existing engine module in
`app/` and shapes the result for HTTP. Conversational endpoints stream tokens
over Server-Sent Events (SSE); everything else is plain JSON.

Prometheus metrics are exposed at GET /metrics (see app/metrics.py + monitoring/).

Run (dev):   uvicorn app.api:app --reload
Run (prod):  uvicorn app.api:app --host 0.0.0.0 --port 8000
In production the built React SPA in frontend/dist is served at "/".
"""

import json
import logging
import tempfile
import time
import threading
from contextlib import asynccontextmanager
from collections.abc import Iterator
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import chain as lcel_chain
from app import code_assistant
from app import flashcards as fc
from app import graph as langgraph_module
from app import metrics
from app import profile as profile_store
from app import quiz_agent
from app.analysis import get_chat_models, get_installed_models, pull_model
from app.api_models import (
    AgentRequest,
    CardInput,
    ChatRequest,
    ClearResponse,
    CodeChatRequest,
    CountResponse,
    CreateDeckRequest,
    Deck,
    DecksResponse,
    ExplainRequest,
    ExplainResponse,
    GenerateDeckRequest,
    HealthResponse,
    IngestResponse,
    ModelsResponse,
    PullRequest,
    PullResponse,
    QuizGenerateRequest,
    QuizValidateRequest,
    ScrapeRequest,
    SourcesResponse,
)
from app.config import get_settings
from app.model_catalog import catalogue, require_model
from app.coach import router as coach_router
from app.public_site import router as public_router
from app.auth import router as auth_router, WorkspaceAuth
from app.limits import consume
from app.diagnostics import router as diagnostics_router, RequestDiagnostics, configure_logging
from app.jobs import router as jobs_router, worker_loop
from fastapi import Request
from app.ingestion import IMAGE_EXTENSIONS
from app.exports import router as exports_router
from app.drawings import router as drawings_router
from app.llm import ModelServiceUnavailable
from app.metering import ActionLimitExceeded
from app.metered import BillingMiddleware
from app.workspace import workspace_id
from app.safety import SafetyError
from fastapi.responses import JSONResponse
from app.extraction import extract as load_and_chunk_image, extract as load_and_chunk_pdf
from app.upload_safety import validate_upload
from app.memory import clear_history
from app.quiz import explain_concept, generate_questions, validate_answer
from app.scraper import search_and_scrape
from app.vectorstore import (
    clear_vectorstore,
    get_doc_count,
    ingest_documents,
    list_sources,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
)
logger = logging.getLogger(__name__)
configure_logging()

@asynccontextmanager
async def lifespan(app):
    stopped = threading.Event()
    thread = None
    if get_settings().embedded_worker:
        thread = threading.Thread(target=worker_loop, args=(stopped,), daemon=True)
        thread.start()
    yield
    stopped.set()
    if thread:
        thread.join(timeout=5)


app = FastAPI(title="PreparationPalAI", version="1.1.0", lifespan=lifespan)
app.include_router(coach_router)
app.include_router(public_router)
app.include_router(auth_router)
from app.account import router as account_router  # noqa: E402
app.include_router(account_router)
app.include_router(diagnostics_router)
app.include_router(jobs_router)
app.include_router(exports_router)
app.include_router(drawings_router)


@app.exception_handler(SafetyError)
async def safety_error_handler(request, exc):
    return JSONResponse(status_code=422, content={'detail': str(exc)})


@app.exception_handler(ActionLimitExceeded)
async def action_limit_handler(request, exc):
    return JSONResponse(status_code=422, content={'detail': str(exc)})


@app.exception_handler(ModelServiceUnavailable)
async def model_unavailable_handler(request, exc):
    return JSONResponse(status_code=503, content={'detail': str(exc)}, headers={'Retry-After': '10'})


# Innermost: rate-limited requests (429) never reserve credits. Runs inside workspace auth.
app.add_middleware(BillingMiddleware)


@app.middleware('http')
async def budget_requests(request: Request, call_next):
    # The auth middleware is installed outermost below, so budgets use trusted identity.
    if request.method == 'POST' and request.url.path.startswith('/api/'):
        from starlette.concurrency import run_in_threadpool
        try:
            await run_in_threadpool(consume)
        except HTTPException as exc:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': exc.detail}, exc.status_code, headers=exc.headers)
    return await call_next(request)

# Dev: Vite serves the SPA on :5173 and proxies /api here. Allow it for CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(WorkspaceAuth)
app.add_middleware(RequestDiagnostics)

# Default HTTP metrics (request count + latency per route) at GET /metrics.
# Exposed before the SPA mount so "/" never shadows it.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


def _set_kb_gauge() -> None:
    try:
        metrics.KB_CHUNKS.set(get_doc_count())
    except Exception:  # noqa: BLE001
        pass


# ── SSE helper ────────────────────────────────────────────────────────────────


def _sse(events: Iterator[tuple[str, object]], surface: str) -> StreamingResponse:
    """Wrap an engine generator of (kind, payload) tuples as an SSE response.

    Emits one JSON object per event, then a terminal {"type":"done"} frame.
    Records per-surface latency, token throughput, and success/error counts.
    """

    def gen() -> Iterator[str]:
        start = time.perf_counter()
        status = "success"
        try:
            for kind, payload in events:
                if kind == "token":
                    metrics.STREAM_TOKENS.labels(surface).inc()
                    frame = {"type": "token", "text": payload}
                elif kind == "sources":
                    frame = {"type": "sources", "sources": payload}
                elif kind == "tool":
                    frame = {"type": "tool", "name": payload}
                elif kind == "questions":
                    frame = {"type": "questions", "questions": payload}
                elif kind == "error":
                    status = "error"
                    frame = {"type": "error", "message": "Model request failed. Retry or share the request ID with your administrator."}
                else:
                    continue
                yield f"data: {json.dumps(frame)}\n\n"
        except (SafetyError, ModelServiceUnavailable, ActionLimitExceeded) as exc:
            status = 'error'
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        except Exception as exc:  # noqa: BLE001 — surface any engine failure to client
            status = "error"
            logger.exception("SSE stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Model request failed. Retry or share the request ID with your administrator.'})}\n\n"
        finally:
            metrics.LLM_LATENCY.labels(surface).observe(time.perf_counter() - start)
            metrics.LLM_REQUESTS.labels(surface, status).inc()
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Billing (hosted mode) ───────────────────────────────────────────────────

TYPICAL_TOKENS = (2500, 600)   # a typical model call, for "about N credits" estimates


@app.get('/api/billing/balance')
def billing_balance():
    from app import metered
    from app.billing_client import BillingUnavailable
    settings = get_settings()
    if not settings.billing_enabled:
        raise HTTPException(404, 'Billing is not enabled.')
    try:
        client = metered.get_client()
        metered._ensure_started(client, workspace_id.get())      # show the free allowance before the first study action
        b = client.balance(workspace_id.get())
    except BillingUnavailable:
        raise HTTPException(503, 'Billing is temporarily unavailable. Please retry.') from None
    return {'available_credits': b['available_micros'] // 1000, 'reserved_credits': b['reserved_micros'] // 1000,
            'starter_credits': b['starter_micros'] // 1000, 'top_up_url': settings.top_up_url}


LEDGER_LABELS = {'grant': 'Free starter credits', 'topup': 'Credits purchased', 'settle': 'Study activity',
                 'refund': 'Refund', 'adjust': 'Adjustment'}


def _require_billing():
    if not get_settings().billing_enabled:
        raise HTTPException(404, 'Billing is not enabled.')
    from app import metered
    return metered.get_client()


@app.get('/api/billing/packs')
def billing_packs(channel: str = Query('web', pattern='^(web|store)$')):
    """Credit packs: `web` (Paddle) or `store` (Apple/Google, with the store product id the phone app buys)."""
    from app.billing_client import BillingUnavailable
    client = _require_billing()
    try:
        packs = client.packs(channel)
    except BillingUnavailable:
        raise HTTPException(503, 'Billing is temporarily unavailable. Please retry.') from None
    shown = []
    for p in packs:
        entry = {'id': p['id'], 'price': f"${p['usd_cents'] / 100:g}", 'credits': p['credits'], 'available': p['available']}
        if channel == 'store':
            entry['product_id'] = p.get('product_id')
        shown.append(entry)
    return {'packs': shown}


class CheckoutRequest(BaseModel):
    pack: str = Field(min_length=1, max_length=40)


CHECKOUT_ERRORS = {403: 'This account has been closed.', 422: 'That credit pack is not available.',
                   503: 'Buying credits is not available yet.', 502: 'The payment provider could not start a checkout. Please retry.'}


@app.post('/api/billing/checkout')
def billing_checkout(req: CheckoutRequest):
    """Start a payment for the signed-in learner. The account is never taken from the request."""
    from app.billing_client import BillingUnavailable
    client = _require_billing()
    try:
        status, body = client.checkout(workspace_id.get(), req.pack)
    except BillingUnavailable:
        raise HTTPException(503, 'Billing is temporarily unavailable. Please retry.') from None
    if status != 200:
        raise HTTPException(status if status in CHECKOUT_ERRORS else 503, CHECKOUT_ERRORS.get(status, CHECKOUT_ERRORS[503]))
    return {k: body[k] for k in ('transaction_id', 'client_token', 'environment')}


@app.get('/api/billing/history')
def billing_history(before_id: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=200)):
    """Purchases, refunds and study charges in plain words. Credit holds are internal and hidden."""
    from app.billing_client import BillingUnavailable
    client = _require_billing()
    try:
        page = client.history(workspace_id.get(), before_id, limit)
    except BillingUnavailable:
        raise HTTPException(503, 'Billing is temporarily unavailable. Please retry.') from None
    entries = []
    for row in page['entries']:
        if row['kind'] in ('reserve', 'release'):
            continue
        label = LEDGER_LABELS.get(row['kind'], 'Adjustment')
        if row['kind'] == 'adjust' and row['ref'].startswith('starter-expiry:'):
            label = 'Free starter credits expired'
        elif row['kind'] == 'adjust' and row['ref'].startswith('reconcile:'):
            label = 'Usage correction'
        entries.append({'id': row['id'], 'when': row['created_at'], 'label': label, 'credits': row['amount_micros'] / 1000})
    return {'entries': entries, 'next_before_id': page['next_before_id']}


@app.get('/api/billing/estimate')
def billing_estimate(action: str, model: str):
    from app import metered
    from app.billing_client import BillingUnavailable, UnpricedModel
    settings = get_settings()
    if not settings.billing_enabled:
        raise HTTPException(404, 'Billing is not enabled.')
    spec = next((s for _, _, s in metered.ROUTES if s.action == action), None)
    if spec is None:
        raise HTTPException(404, 'Unknown action.')
    alias, lines, _ = metered.reservation(spec, {}, model)
    client = metered.get_client()
    try:
        micros = 0
        for line in lines:       # one typical call per reserved line, not the worst case
            tokens_in = min(line['max_input_tokens'], TYPICAL_TOKENS[0])
            tokens_out = min(line['max_output_tokens'], TYPICAL_TOKENS[1])
            micros += client.estimate(line['alias'], tokens_in, tokens_out) * (1 if line['alias'] != alias else max(1, line['calls'] // 2))
    except UnpricedModel:
        raise HTTPException(409, f"Model '{model}' is not available.") from None
    except BillingUnavailable:
        raise HTTPException(503, 'Billing is temporarily unavailable. Please retry.') from None
    return {'credits': max(1, -(-micros // 1000))}


# ── Health / models ─────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    _set_kb_gauge()
    if settings.inference_backend == 'gateway':
        from app.gateway_models import healthy, selectable
        up = healthy()
        metrics.OLLAMA_UP.set(1 if up else 0)
        return HealthResponse(online=up, model_count=len(selectable()) if up else 0)
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        r.raise_for_status()
        models = [m for m in r.json().get("models", []) if "embed" not in m["name"]]
        metrics.OLLAMA_UP.set(1)
        return HealthResponse(online=True, model_count=len(models))
    except Exception:
        metrics.OLLAMA_UP.set(0)
        return HealthResponse(online=False, model_count=0)


@app.get("/api/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    installed = get_installed_models()
    entries = catalogue(installed, get_chat_models())
    return ModelsResponse(
        supported=[m['id'] for m in entries],
        installed=sorted(installed),
        catalogue=entries,
    )


def _require_self_hosted_pulls() -> None:
    if get_settings().inference_backend == 'gateway':
        raise HTTPException(404, 'Model downloads are managed by the hosting provider.')


@app.post("/api/models/pull", response_model=PullResponse)
def models_pull(req: PullRequest) -> PullResponse:
    _require_self_hosted_pulls()
    ok, message = pull_model(req.model)
    return PullResponse(ok=ok, message=message)


@app.post('/api/models/pull/stream')
def models_pull_stream(req: PullRequest):
    _require_self_hosted_pulls()
    def frames():
        try:
            with httpx.stream('POST', f'{get_settings().ollama_base_url}/api/pull',
                              json={'name': req.model, 'stream': True}, timeout=900) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    body = json.loads(line)
                    if body.get('error'):
                        raise ValueError('Model unavailable')
                    frame = dict(type='progress', status=str(body.get('status', 'Downloading'))[:100],
                                 completed=max(0, int(body.get('completed', 0))),
                                 total=max(0, int(body.get('total', 0))))
                    yield f'data: {json.dumps(frame)}\n\n'
        except Exception:
            yield 'data: {"type":"error","message":"Download failed. Check the model tag and Ollama connection."}\n\n'
        yield 'data: {"type":"done"}\n\n'
    return StreamingResponse(frames(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ── Knowledge base ────────────────────────────────────────────────────────────


@app.get("/api/kb/count", response_model=CountResponse)
def kb_count() -> CountResponse:
    count = get_doc_count()
    metrics.KB_CHUNKS.set(count)
    return CountResponse(count=count)


@app.get("/api/kb/sources", response_model=SourcesResponse)
def kb_sources() -> SourcesResponse:
    """List the files/URLs currently in the knowledge base with chunk counts."""
    return SourcesResponse(sources=list_sources())


@app.post("/api/kb/upload", response_model=IngestResponse)
async def kb_upload(files: list[UploadFile] = File(...)) -> IngestResponse:
    if get_settings().production:
        raise HTTPException(409, 'Use /api/kb/jobs/upload for queued ingestion')
    if len(files) > get_settings().upload_max_files:
        raise HTTPException(413, 'Too many files in one upload')
    total = 0
    details: list[str] = []
    for f in files:
        name = Path((f.filename or 'file').replace('\\', '/')).name
        ext = Path(name).suffix.lower()
        is_pdf = ext == ".pdf"
        is_image = ext in IMAGE_EXTENSIONS
        if not (is_pdf or is_image):
            details.append(f"{name}: skipped (unsupported type)")
            continue
        data = await f.read(get_settings().upload_max_bytes + 1)
        try:
            validate_upload(data, name, f.content_type or 'application/octet-stream')
        except ValueError as exc:
            raise HTTPException(413 if len(data) > get_settings().upload_max_bytes else 415, str(exc)) from None
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            # Preserve the original filename as the KB source label.
            if is_pdf:
                chunks = load_and_chunk_pdf(tmp_path, source_name=name)
            else:
                chunks = load_and_chunk_image(tmp_path, source_name=name)
            if not chunks:
                details.append(f"{name}: no readable text found")
                continue
            n = ingest_documents(chunks)
            total += n
            details.append(f"{name}: {n} chunks")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Upload failed for %s", name)
            details.append(f"{name}: failed — {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)
    _set_kb_gauge()
    return IngestResponse(chunks_added=total, detail="; ".join(details))


@app.post("/api/kb/scrape", response_model=IngestResponse)
def kb_scrape(req: ScrapeRequest) -> IngestResponse:
    if get_settings().production:
        raise HTTPException(409, 'Use /api/kb/jobs/scrape for queued ingestion')
    try:
        chunks = search_and_scrape(req.topic.strip(), num_results=req.num_results)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scrape failed")
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc
    if not chunks:
        return IngestResponse(chunks_added=0, detail="No content found.")
    n = ingest_documents(chunks)
    _set_kb_gauge()
    return IngestResponse(chunks_added=n, detail=f"Added {n} chunks from web.")


@app.delete("/api/kb", response_model=ClearResponse)
def kb_clear() -> ClearResponse:
    clear_vectorstore()
    metrics.KB_CHUNKS.set(0)
    return ClearResponse(cleared=True)


# ── Chat (Regular Chat, RAG) — streaming ────────────────────────────────────


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    req.model = require_model(req.model)
    if req.mode == "langgraph":
        events = langgraph_module.stream(
            question=req.question,
            thread_id=req.session_id,
            model=req.model,
            top_k=req.top_k,
            profile=profile_store.tailor(req.profile),
        )
    else:
        events = lcel_chain.stream(
            question=req.question,
            session_id=req.session_id,
            model=req.model,
            top_k=req.top_k,
            profile=profile_store.tailor(req.profile),
        )
    return _sse(events, surface="chat")


@app.delete("/api/chat/{session_id}", response_model=ClearResponse)
def chat_clear(session_id: str) -> ClearResponse:
    clear_history(session_id)
    return ClearResponse(cleared=True)


# ── Programming assistant — streaming ───────────────────────────────────────


@app.post("/api/code-chat/stream")
def code_chat_stream(req: CodeChatRequest) -> StreamingResponse:
    req.model = require_model(req.model)
    events = code_assistant.stream_code_assistant(
        message=req.message,
        thread_id=req.thread_id,
        model=req.model,
        use_kb=req.use_kb,
        profile=profile_store.tailor(req.profile),
    )
    return _sse(events, surface="code")


# ── Study agent — streaming ─────────────────────────────────────────────────


@app.post("/api/agent/stream")
def agent_stream(req: AgentRequest) -> StreamingResponse:
    req.model = require_model(req.model)
    events = quiz_agent.stream_agent(
        message=req.message, thread_id=req.thread_id, model=req.model, profile=profile_store.tailor(req.profile),
        allow_web=req.allow_web
    )
    return _sse(events, surface="agent")


# ── Quiz ───────────────────────────────────────────────────────────────────


@app.post("/api/quiz/generate")
def quiz_generate(req: QuizGenerateRequest) -> list[dict]:
    req.model = require_model(req.model)
    start = time.perf_counter()
    status = "success"
    try:
        return generate_questions(
            topic=req.topic.strip(),
            question_type=req.question_type,
            n=req.n,
            difficulty=req.difficulty,
            exam_type=req.exam_type,
            model=req.model,
            top_k=get_settings().quiz_top_k,
            profile=profile_store.tailor(req.profile),
        )
    except Exception:
        status = "error"
        raise
    finally:
        metrics.LLM_LATENCY.labels("quiz").observe(time.perf_counter() - start)
        metrics.LLM_REQUESTS.labels("quiz", status).inc()


@app.post("/api/quiz/validate")
def quiz_validate(req: QuizValidateRequest) -> dict:
    if req.question_type == 'short_answer':
        req.model = require_model(req.model)
    result = validate_answer(
        question=req.question,
        correct_answer=req.correct_answer,
        student_answer=req.student_answer,
        profile=profile_store.tailor(req.profile),
        question_type=req.question_type,
        model=req.model,
    )
    if result.get('feedback', '').startswith('Could not grade answer:'):
        raise HTTPException(502, 'The model could not grade this answer. Retry or choose another model; no score has been awarded.')
    return result


@app.post("/api/quiz/explain", response_model=ExplainResponse)
def quiz_explain(req: ExplainRequest) -> ExplainResponse:
    req.model = require_model(req.model)
    return ExplainResponse(explanation=explain_concept(req.concept, model=req.model, profile=profile_store.tailor(req.profile)))


# ── Flashcards ─────────────────────────────────────────────────────────────


@app.get("/api/profile", response_model=profile_store.StoredProfile, tags=["Profile"])
def profile_get() -> profile_store.StoredProfile:
    """The signed-in learner's profile (defaults with `onboarded: false` before they set it up)."""
    return profile_store.load()


@app.put("/api/profile", response_model=profile_store.StoredProfile, tags=["Profile"])
def profile_put(req: profile_store.LearnerProfile) -> profile_store.StoredProfile:
    """Replace the signed-in learner's profile. AI requests without their own profile use it."""
    return profile_store.save(req)


@app.get("/api/flashcards", response_model=DecksResponse)
def flashcards_list() -> DecksResponse:
    return DecksResponse(decks=fc.list_decks())


@app.post("/api/flashcards", response_model=Deck)
def flashcards_create(req: CreateDeckRequest) -> Deck:
    return Deck(**fc.create_deck(req.name))


@app.post("/api/flashcards/generate", response_model=Deck)
def flashcards_generate(req: GenerateDeckRequest) -> Deck:
    req.model = require_model(req.model)
    start = time.perf_counter()
    status = "success"
    try:
        return Deck(**fc.generate_deck(req.topic, n=req.n, model=req.model, deck_name=req.deck_name, profile=profile_store.tailor(req.profile)))
    except Exception:
        status = "error"
        raise
    finally:
        metrics.LLM_LATENCY.labels("flashcards").observe(time.perf_counter() - start)
        metrics.LLM_REQUESTS.labels("flashcards", status).inc()


@app.get("/api/flashcards/{deck_id}", response_model=Deck)
def flashcards_get(deck_id: str) -> Deck:
    deck = fc.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return Deck(**deck)


@app.delete("/api/flashcards/{deck_id}", response_model=ClearResponse)
def flashcards_delete(deck_id: str) -> ClearResponse:
    if not fc.delete_deck(deck_id):
        raise HTTPException(status_code=404, detail="Deck not found")
    return ClearResponse(cleared=True)


@app.post("/api/flashcards/{deck_id}/cards", response_model=Deck)
def flashcards_add_card(deck_id: str, req: CardInput) -> Deck:
    if fc.add_card(deck_id, req.front, req.back) is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    return Deck(**fc.get_deck(deck_id))


@app.put("/api/flashcards/{deck_id}/cards/{card_id}", response_model=Deck)
def flashcards_update_card(deck_id: str, card_id: str, req: CardInput) -> Deck:
    if fc.update_card(deck_id, card_id, req.front, req.back) is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return Deck(**fc.get_deck(deck_id))


@app.delete("/api/flashcards/{deck_id}/cards/{card_id}", response_model=Deck)
def flashcards_delete_card(deck_id: str, card_id: str) -> Deck:
    if not fc.delete_card(deck_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return Deck(**fc.get_deck(deck_id))


# ── Static SPA (production) ─────────────────────────────────────────────────
# Mounted last so it never shadows /api routes. Real files (e.g. /assets/*) are
# served directly; any other path falls back to index.html so client-side
# routing (BrowserRouter deep links like /quiz) works. Only mounted if a build
# exists — otherwise the API runs standalone behind the Vite dev server.

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


import mimetypes  # noqa: E402

mimetypes.add_type('application/manifest+json', '.webmanifest')

# Client-side routes: a reload or a sign-in redirect to these must load the app, not 404.
CLIENT_ROUTES = {'prepare', 'quiz', 'agent', 'code', 'chat', 'flashcards', 'guide', 'drawings', 'account', 'auth'}
NO_CACHE = {'index.html', 'sw.js', 'sw-strategy.js', 'manifest.webmanifest'}


class SPAStaticFiles(StaticFiles):
    """Serves the built web app: index.html for client routes, correct headers for the PWA files."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
            name = path.strip('/') or 'index.html'
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and path.strip('/').split('/')[0] in CLIENT_ROUTES:
                response, name = await super().get_response("index.html", scope), 'index.html'
            else:
                raise
        if name in NO_CACHE or name.endswith('/index.html'):
            response.headers['Cache-Control'] = 'no-cache'        # always revalidate the shell and the worker
        elif name.startswith('assets/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'   # content-hashed by Vite
        if name == 'sw.js':
            response.headers['Service-Worker-Allowed'] = '/'
        return response


if _DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(_DIST), html=True), name="spa")
    logger.info("Serving SPA from %s", _DIST)
else:
    logger.info("No SPA build at %s — API-only mode (use Vite dev server).", _DIST)
