"""Request identity propagated to thread-pool and streaming operations."""
from contextvars import ContextVar

workspace_id: ContextVar[str] = ContextVar('workspace_id', default='local')
identity_id: ContextVar[str] = ContextVar('identity_id', default='local')
request_id: ContextVar[str] = ContextVar('request_id', default='-')


def scoped_thread(value: str) -> str:
    workspace = workspace_id.get()
    return value if workspace == 'local' else f'{workspace}:{value}'
