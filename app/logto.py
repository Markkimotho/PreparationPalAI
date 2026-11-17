"""Remove a learner's sign-in from Logto through its management API. Optional."""
import re

import httpx

from app.config import get_base_settings

SAFE_SUBJECT = re.compile(r'^[A-Za-z0-9_.~-]{1,128}$')


class LogtoError(Exception):
    pass


def configured() -> bool:
    s = get_base_settings()
    return bool(s.logto_endpoint and s.logto_management_app_id and s.logto_management_app_secret.get_secret_value())


def delete_user(subject: str, client: httpx.Client | None = None) -> None:
    """Delete the user. A user that is already gone counts as success."""
    if not SAFE_SUBJECT.fullmatch(subject or '') or subject in ('.', '..'):
        raise LogtoError('Unsafe user id')
    s = get_base_settings()
    http = client or httpx.Client(base_url=s.logto_endpoint.rstrip('/'), timeout=10)
    try:
        token = http.post('/oidc/token', auth=(s.logto_management_app_id, s.logto_management_app_secret.get_secret_value()),
                          data={'grant_type': 'client_credentials', 'resource': 'https://default.logto.app/api', 'scope': 'all'})
        if token.status_code != 200:
            raise LogtoError('Could not authorise with the sign-in service')
        response = http.delete(f'/api/users/{subject}', headers={'Authorization': f"Bearer {token.json()['access_token']}"})
        if response.status_code not in (200, 204, 404):
            raise LogtoError('The sign-in service refused to delete the user')
    except httpx.HTTPError as exc:
        raise LogtoError('The sign-in service is unreachable') from exc
