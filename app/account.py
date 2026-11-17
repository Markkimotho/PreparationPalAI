"""Account deletion for signed-in learners."""
import logging

from fastapi import APIRouter, HTTPException, Response

from app import logto, purge
from app.billing_client import BillingUnavailable
from app.config import get_base_settings
from app.workspace import account_subject, workspace_id

router = APIRouter(prefix='/api/account', tags=['Account'])
logger = logging.getLogger(__name__)


@router.delete('', status_code=204)
def delete_account():
    """Close billing, remove every stored study item, then remove the sign-in. Safe to repeat.

    Order matters: billing is closed first so nothing new can be charged while data is removed
    (if billing is down nothing is touched and the learner retries); the sign-in goes last so a
    failure there leaves a clean, empty account that can simply retry.
    """
    settings = get_base_settings()
    if settings.auth_mode != 'oidc':
        raise HTTPException(403, 'Account deletion is only available to signed-in learners.')
    workspace = workspace_id.get()
    if settings.billing_enabled:
        from app import metered
        try:
            metered.get_client().close_account(workspace)
        except BillingUnavailable:
            raise HTTPException(503, 'Billing is temporarily unavailable. Nothing was deleted; please retry.') from None
    try:
        purge.purge_workspace(workspace)
    except purge.PurgeIncomplete as exc:
        logger.error('Account purge incomplete', extra={'stores': exc.failed})
        raise HTTPException(500, 'Some of your data could not be removed yet. Please retry.') from None
    subject = account_subject.get()
    if subject and logto.configured():
        try:
            logto.delete_user(subject)
        except logto.LogtoError:
            raise HTTPException(502, 'Your data was removed but your sign-in could not be deleted yet. Please retry.') from None
    return Response(status_code=204)
