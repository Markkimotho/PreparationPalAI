"""Allowlisted structured diagnostics: never serialize prompts, URLs or exceptions."""
import json
import logging
import re
import time
import uuid

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram

from app.config import get_settings
from app.workspace import request_id, workspace_id

router = APIRouter(tags=['Operations'])
HTTP_REQUESTS = Counter('preparationpalai_requests_total', 'Requests by route, workspace and outcome', ['route', 'workspace', 'status'])
HTTP_SECONDS = Histogram('preparationpalai_request_seconds', 'Complete HTTP/SSE latency', ['route'])
DEPENDENCY_UP = Counter('preparationpalai_readiness_failures_total', 'Readiness dependency failures', ['dependency'])
RETRIEVAL_FAILURES = Counter('preparationpalai_retrieval_failures_total', 'Retrieval failures')
FRONTEND_ERRORS = Counter('preparationpalai_frontend_errors_total', 'Sanitized frontend errors', ['kind'])


class SafeFormatter(logging.Formatter):
    def format(self, record):
        event = record.msg if isinstance(record.msg, str) and re.fullmatch(r'[a-z_.]{1,80}', record.msg) else 'application_event'
        value = dict(level=record.levelname, logger=record.name, event=event,
                     request_id=request_id.get(), workspace=workspace_id.get())
        if record.exc_info:
            value['error_type'] = record.exc_info[0].__name__
        for key in ('route', 'status', 'elapsed_ms'):
            if hasattr(record, key):
                value[key] = getattr(record, key)
        return json.dumps(value)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger('uvicorn.access').disabled = True
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


class RequestDiagnostics:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # Generate server-owned IDs; client input cannot inject log content.
        rid = uuid.uuid4().hex
        token = request_id.set(rid)
        started = time.monotonic()
        status, workspace = 500, 'local'

        async def observed_send(message):
            nonlocal status, workspace
            if message['type'] == 'http.response.start':
                status = message['status']
                workspace = workspace_id.get()
                message['headers'] = [*message.get('headers', []), (b'x-request-id', rid.encode())]
            await send(message)
        try:
            await self.app(scope, receive, observed_send)
        finally:
            route = getattr(scope.get('route'), 'path', 'unmatched')
            elapsed = time.monotonic() - started
            HTTP_REQUESTS.labels(route, workspace, str(status)).inc()
            HTTP_SECONDS.labels(route).observe(elapsed)
            wtoken = workspace_id.set(workspace)
            logging.getLogger('app.requests').info('request_complete', extra=dict(route=route, status=status, elapsed_ms=round(elapsed * 1000)))
            workspace_id.reset(wtoken)
            request_id.reset(token)


@router.get('/health/live', include_in_schema=False)
def live():
    return {'alive': True}


@router.get('/health/ready', include_in_schema=False)
def ready():
    settings = get_settings()
    dependencies = {'ollama': False, 'chat_model': False, 'embedding_model': False, 'vectorstore': False}
    try:
        result = httpx.get(f'{settings.ollama_base_url}/api/tags', timeout=3)
        result.raise_for_status()
        names = {m['name'] for m in result.json()['models']}
        dependencies['ollama'] = True
        dependencies['chat_model'] = settings.ollama_model in names or f'{settings.ollama_model}:latest' in names
        dependencies['embedding_model'] = settings.ollama_embedding_model in names or f'{settings.ollama_embedding_model}:latest' in names
    except Exception:
        pass
    try:
        from app.vectorstore import get_vectorstore
        get_vectorstore()._collection.count()
        dependencies['vectorstore'] = True
    except Exception:
        pass
    for name, up in dependencies.items():
        if not up:
            DEPENDENCY_UP.labels(name).inc()
    success = all(dependencies.values())
    from app.metrics import OLLAMA_UP
    OLLAMA_UP.set(dependencies['ollama'])
    return JSONResponse({'ready': success, 'dependencies': dependencies}, 200 if success else 503)


@router.post('/api/diagnostics/frontend')
def frontend_error(body: dict):
    kind = body.get('kind')
    if kind not in ('script', 'unhandled-rejection', 'network'):
        return JSONResponse({'detail': 'Unknown diagnostic category'}, 422)
    FRONTEND_ERRORS.labels(kind).inc()
    return {'recorded': True, 'request_id': request_id.get()}
