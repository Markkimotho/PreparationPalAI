"""Bill every model-backed request: reserve before it runs, settle the real usage after.

One ASGI middleware covers JSON and streaming routes alike. It runs inside workspace
authentication (so it knows who is paying), reserves credits through the billing service
(402 if the learner cannot afford the action), binds a usage meter for the whole request,
and settles when the response finishes or the client disconnects. A route table decides
what each route reserves; `tests/test_billing_wiring.py` fails the build for any POST route
that is neither listed here nor explicitly exempt, so a new model route cannot ship unbilled.

Reservations are an estimate: usage above the hold is charged from the balance afterwards.
A per-action cap on model calls stops runaway loops (the call that crosses the cap is kept
and charged).
"""
import json
import logging
import math
import re
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import anyio
from fastapi import HTTPException
from starlette.responses import JSONResponse

from app import billing_outbox
from app.billing_client import (AccountClosed, BillingUnavailable, CreditsRequired, ReservationMissing, UnpricedModel, get_client)
from app.config import get_settings
from app.metering import ActionLimitExceeded, Meter, UsageRecord, bind
from app.workspace import account_email, email_verified, workspace_id

logger = logging.getLogger(__name__)

GUARD_PER_MAIN = 3          # input check, output check, verification
GUARD_SLACK = 3
GUARD_OUTPUT_TOKENS = 64


def _batches(n_field: str, default: int):
    return lambda body: 2 * math.ceil(int(body.get(n_field, default) or default) / 2)   # batches of 2, one retry each


@dataclass(frozen=True)
class Spec:
    action: str
    calls: Callable[[dict], int] = lambda body: 1       # main model calls the action may make
    kind: str = 'model'                                 # model | guard | vision | embed
    vision_calls: int = 0


ROUTES: list[tuple[str, re.Pattern, Spec]] = [(m, re.compile(p + r'/?$'), s) for m, p, s in [
    ('POST', r'/api/chat/stream', Spec('chat', lambda b: 2)),   # rephrase with history, then answer
    ('POST', r'/api/code-chat/stream', Spec('code_chat')),
    ('POST', r'/api/agent/stream', Spec('agent', lambda b: 12)),
    ('POST', r'/api/quiz/generate', Spec('quiz_generate', _batches('n', 10))),
    ('POST', r'/api/quiz/validate', Spec('quiz_validate', lambda b: 1 if b.get('question_type') == 'short_answer' else 0)),
    ('POST', r'/api/quiz/explain', Spec('quiz_explain')),
    ('POST', r'/api/flashcards/generate', Spec('flashcards_generate', _batches('n', 10))),
    ('POST', r'/api/coach/sessions', Spec('coach_start', _batches('n', 5))),
    ('POST', r'/api/coach/sessions/[^/]+/answers', Spec('coach_answer', lambda b: 3)),
    ('POST', r'/api/exports/study', Spec('export', kind='guard')),
    ('POST', r'/api/drawings', Spec('drawing_submit', kind='guard')),
    ('POST', r'/api/drawings/[^/]+/review', Spec('drawing_review', kind='guard')),
    ('POST', r'/api/drawings/[^/]+/ai-review', Spec('drawing_ai_review', kind='vision', vision_calls=2)),
    ('POST', r'/api/kb/upload', Spec('kb_upload', kind='embed')),
    ('POST', r'/api/kb/scrape', Spec('kb_scrape', kind='embed')),
]]

# POST routes that never call a model: enqueue-only, local state, or administrative.
EXEMPT = [(m, re.compile(p + r'/?$')) for m, p in [
    ('POST', r'/api/diagnostics/frontend'),
    ('POST', r'/api/flashcards'),
    ('POST', r'/api/flashcards/[^/]+/cards'),
    ('POST', r'/api/kb/jobs/(upload|scrape)'),          # queued; the worker meters the embedding work
    ('POST', r'/api/kb/jobs/[^/]+/retry'),
    ('POST', r'/api/models/pull(/stream)?'),
    ('POST', r'/api/billing/checkout'),                 # starts a payment; no model work
]]


def spec_for(method: str, path: str) -> Spec | None:
    return next((s for m, rx, s in ROUTES if m == method and rx.match(path)), None)


def is_metered(method: str, path: str) -> bool:
    return spec_for(method, path) is not None


def is_exempt(method: str, path: str) -> bool:
    return any(m == method and rx.match(path) for m, rx in EXEMPT)


def reservation(spec: Spec, body: dict, requested_model: str | None) -> tuple[str, list[dict], dict[str, int]]:
    """The tier alias, the priced lines to reserve, and the per-purpose call caps for this action."""
    s = get_settings()
    inp, out = s.billing_reserve_input_tokens, s.billing_reserve_output_tokens
    guard = lambda calls: dict(alias=s.guard_alias, max_input_tokens=inp, max_output_tokens=GUARD_OUTPUT_TOKENS, calls=calls)
    if spec.kind == 'guard':
        return s.guard_alias, [guard(2 + GUARD_SLACK)], {'guard': 2 + GUARD_SLACK}
    if spec.kind == 'embed':
        return s.embedding_alias, [dict(alias=s.embedding_alias, max_input_tokens=s.ingest_reserve_tokens, max_output_tokens=0, calls=1)], {}
    if spec.kind == 'vision':
        lines = [dict(alias=s.vision_alias, max_input_tokens=inp + 2000, max_output_tokens=1200, calls=spec.vision_calls), guard(2 + GUARD_SLACK)]
        return s.vision_alias, lines, {'vision': spec.vision_calls, 'guard': 2 + GUARD_SLACK}
    alias = requested_model or s.ollama_model
    calls = spec.calls(body)
    lines = [dict(alias=alias, max_input_tokens=inp, max_output_tokens=out, calls=calls),
             guard(GUARD_PER_MAIN * calls + GUARD_SLACK)]
    return alias, lines, {'main': calls, 'guard': GUARD_PER_MAIN * calls + GUARD_SLACK}


def breaker(caps: dict[str, int]) -> Callable[[UsageRecord], None]:
    counts: Counter = Counter()

    def on_add(usage: UsageRecord) -> None:
        counts[usage.purpose] += 1
        if usage.purpose in caps and counts[usage.purpose] > caps[usage.purpose]:
            raise ActionLimitExceeded()
    return on_add


def aggregate(records: list[UsageRecord]) -> list[dict]:
    totals: dict[str, list[int]] = {}
    for r in records:
        t = totals.setdefault(r.alias, [0, 0])
        t[0] += r.input_tokens
        t[1] += r.output_tokens
    return [dict(alias=a, input_tokens=i, output_tokens=o) for a, (i, o) in totals.items()]


_started: set[str] = set()


SETTLED_GRANT_OUTCOMES = {'granted', 'already_granted', 'email_in_use', 'disposable_email'}


def _ensure_started(client, account_id: str) -> None:
    """Offer the free allowance once per account. Billing decides; the learner's email must be verified."""
    if account_id in _started:
        return
    try:
        result = client.grant_starter(account_id, account_email.get(), email_verified.get())     # idempotent on the billing side
    except BillingUnavailable:
        return                                     # the reservation below will fail closed if billing is really down
    if result.get('reason') in SETTLED_GRANT_OUTCOMES:
        _started.add(account_id)                   # an unverified learner is asked again after they verify


@dataclass
class Hold:
    request_id: str
    account_id: str
    meter: Meter


def begin(account_id: str, spec: Spec, body: dict) -> Hold:
    """Reserve credits for one action. Raises CreditsRequired, UnpricedModel or BillingUnavailable."""
    client = get_client()
    try:
        billing_outbox.flush(client)
    except Exception:  # noqa: BLE001 - a stuck outbox must never block new work
        logger.exception('Billing outbox flush failed')
    _ensure_started(client, account_id)
    request_id = uuid.uuid4().hex
    model = body.get('model') if isinstance(body.get('model'), str) else None
    alias, lines, caps = reservation(spec, body, model)
    client.reserve(account_id, request_id, spec.action, alias, lines)
    return Hold(request_id, account_id, Meter(spec.action, request_id, breaker(caps)))


def end(hold: Hold) -> None:
    """Settle what was used, or release the hold if nothing ran. Never raises: usage is queued if billing is down."""
    client = get_client()
    records = hold.meter.records
    try:
        if not records:
            client.release(hold.request_id)
            return
        usage = aggregate(records)
        try:
            client.settle(hold.request_id, usage)
        except BillingUnavailable:
            billing_outbox.enqueue(hold.request_id, usage)
            logger.error('Billing unreachable at settle; usage queued', extra={'request_id': hold.request_id})
        except ReservationMissing:
            logger.error('Billing has no record of this reservation; usage not charged', extra={'request_id': hold.request_id})
    except BillingUnavailable:
        logger.warning('Could not release a hold; the sweeper will', extra={'request_id': hold.request_id})
    except Exception:  # noqa: BLE001
        logger.exception('Unexpected failure while settling', extra={'request_id': hold.request_id})


def credits_response(exc: CreditsRequired) -> JSONResponse:
    detail = ('Premium models use purchased credits. Top up to continue.' if exc.premium_requires_purchase
              else 'Not enough credits for this action.')
    return JSONResponse({'detail': detail, 'balance_credits': exc.balance_micros // 1000,
                         'required_credits': -(-exc.required_micros // 1000), 'top_up_url': get_settings().top_up_url}, 402)


async def _buffer(receive):
    messages, body = [], b''
    while True:
        message = await receive()
        messages.append(message)
        if message['type'] != 'http.request':
            break
        body += message.get('body', b'')
        if not message.get('more_body'):
            break
    return messages, body


class BillingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        spec = spec_for(scope.get('method', ''), scope.get('path', '')) if scope['type'] == 'http' else None
        if spec is None or not get_settings().billing_enabled:
            return await self.app(scope, receive, send)
        body: dict = {}
        if b'json' in dict(scope['headers']).get(b'content-type', b''):
            messages, raw = await _buffer(receive)
            try:
                body = json.loads(raw or b'{}')
                body = body if isinstance(body, dict) else {}
            except ValueError:
                body = {}
            replay = list(messages)

            async def receive_again():
                return replay.pop(0) if replay else await receive()
            downstream_receive = receive_again
        else:
            downstream_receive = receive
        if spec.kind == 'model' and spec.calls(body) == 0:
            return await self.app(scope, downstream_receive, send)      # deterministic grading: nothing to bill
        try:
            hold = await anyio.to_thread.run_sync(begin, workspace_id.get(), spec, body)
        except CreditsRequired as exc:
            return await credits_response(exc)(scope, downstream_receive, send)
        except AccountClosed:
            return await JSONResponse({'detail': 'This account has been closed.'}, 403)(scope, downstream_receive, send)
        except UnpricedModel as exc:
            return await JSONResponse({'detail': f"Model '{exc.alias}' is not available."}, 409)(scope, downstream_receive, send)
        except BillingUnavailable:
            return await JSONResponse({'detail': 'Billing is temporarily unavailable. Please retry.'}, 503,
                                      headers={'Retry-After': '10'})(scope, downstream_receive, send)
        try:
            with bind(hold.meter):
                await self.app(scope, downstream_receive, send)
        finally:
            with anyio.CancelScope(shield=True):          # settle even if the client disconnected
                await anyio.to_thread.run_sync(end, hold)


def job_scope(account_id: str, action: str):
    """Meter background work (the ingestion worker). A no-op context when billing is disabled."""
    from contextlib import contextmanager

    @contextmanager
    def scope():
        spec = next((s for _, _, s in ROUTES if s.action == action), None)
        if spec is None or not get_settings().billing_enabled:
            yield
            return
        try:
            hold = begin(account_id, spec, {})
        except CreditsRequired:
            raise HTTPException(402, 'Not enough credits to process this upload. Top up and retry.') from None
        except (BillingUnavailable, UnpricedModel) as exc:
            raise RuntimeError('Billing is unavailable') from exc
        try:
            with bind(hold.meter):
                yield
        finally:
            end(hold)
    return scope()
