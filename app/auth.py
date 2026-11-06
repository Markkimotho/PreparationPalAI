"""Bearer-key workspace authentication. Revocation takes effect on the next request."""
import hashlib
import hmac

from fastapi import APIRouter
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import get_base_settings
from app.workspace import workspace_id, identity_id, role

router = APIRouter(prefix='/api/auth', tags=['Access'])


@router.get('/status')
def status():
    return {'enabled': get_base_settings().auth_enabled}


@router.get('/me')
def me():
    return {'workspace': workspace_id.get(), 'identity': identity_id.get()}


def mutation(path: str, method: str) -> bool:
    return method not in ('GET', 'HEAD', 'OPTIONS') and (
        path.startswith('/api/kb') or path.startswith('/api/flashcards') or
        path.startswith('/api/models/pull'))


class WorkspaceAuth:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        settings = get_base_settings()
        path = scope['path']
        headers = dict(scope['headers'])
        limit = 64 * 1024 * 1024 if path in ('/api/kb/upload', '/api/kb/jobs/upload') else settings.request_max_bytes
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, 400)(scope, receive, send)
        if path.startswith('/api/') and length > limit:
            return await JSONResponse({'detail': 'Request body is too large.'}, 413)(scope, receive, send)
        original_receive = receive
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await original_receive()
            received += len(message.get('body', b''))
            if path.startswith('/api/') and received > limit:
                raise HTTPException(413, 'Request body is too large.')
            return message
        protected = (path.startswith('/api/') and path != '/api/auth/status') or path == '/metrics'
        workspace, identity = 'local', 'local'
        if settings.auth_enabled and protected and scope['method'] != 'OPTIONS':
            header = headers.get(b'authorization', b'').decode('latin-1')
            raw = header[7:] if header.startswith('Bearer ') else ''
            digest = hashlib.sha256(raw.encode()).hexdigest()
            principal = next((v for key, v in settings.auth_tokens.items()
                              if raw and hmac.compare_digest(key, digest)), None)
            if not principal:
                response = JSONResponse({'detail': 'Sign in with a valid workspace access key.'}, 401,
                                        headers={'WWW-Authenticate': 'Bearer'})
                return await response(scope, receive, send)
            if ((mutation(path, scope['method']) and principal['role'] == 'reader') or
                ((path.startswith('/api/models/pull') or path == '/metrics') and principal['role'] != 'admin')):
                return await JSONResponse({'detail': 'Your role cannot perform this operation.'}, 403)(scope, receive, send)
            workspace, identity = principal['workspace'], digest[:16]
        wtoken = workspace_id.set(workspace)
        itoken = identity_id.set(identity)
        rtoken = role.set(principal['role'] if settings.auth_enabled and protected and scope['method'] != 'OPTIONS' else 'admin')
        try:
            await self.app(scope, bounded_receive, send)
        finally:
            workspace_id.reset(wtoken)
            identity_id.reset(itoken)
            role.reset(rtoken)
