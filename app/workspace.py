"""Request identity propagated to thread-pool and streaming operations."""
from contextvars import ContextVar

workspace_id: ContextVar[str] = ContextVar('workspace_id', default='local')
identity_id: ContextVar[str] = ContextVar('identity_id', default='local')
role: ContextVar[str] = ContextVar('role', default='admin')
# Set only for signed-in (OIDC) learners; billing uses them to gate the free starter allowance.
account_email: ContextVar[str | None] = ContextVar('account_email', default=None)
email_verified: ContextVar[bool] = ContextVar('email_verified', default=False)
request_id: ContextVar[str] = ContextVar('request_id', default='-')


def scoped_thread(value: str) -> str:
    workspace = workspace_id.get()
    return value if workspace == 'local' else f'{workspace}:{value}'
