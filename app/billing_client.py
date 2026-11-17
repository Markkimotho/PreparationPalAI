"""Client for the internal billing service (contracts/billing.yaml)."""
import logging
from functools import lru_cache

import httpx

from app.config import get_base_settings

logger = logging.getLogger(__name__)


class BillingUnavailable(RuntimeError):
    """Billing could not be reached or answered with a server error."""


class CreditsRequired(Exception):
    def __init__(self, balance_micros: int, required_micros: int, premium_requires_purchase: bool):
        super().__init__('Not enough credits')
        self.balance_micros, self.required_micros = balance_micros, required_micros
        self.premium_requires_purchase = premium_requires_purchase


class AccountClosed(Exception):
    """The learner deleted their account."""


class UnpricedModel(Exception):
    def __init__(self, alias: str):
        super().__init__(alias)
        self.alias = alias


class ReservationMissing(Exception):
    """Billing has no record of this reservation (for example its database was reset)."""


class BillingClient:
    def __init__(self, base_url: str = '', token: str = '', client: httpx.Client | None = None, timeout: float = 5.0):
        self.http = client or httpx.Client(base_url=base_url, headers={'Authorization': f'Bearer {token}'}, timeout=timeout)

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BillingUnavailable(type(exc).__name__) from exc
        if response.status_code >= 500 or response.status_code == 401:     # 403 is meaningful: the account was closed
            raise BillingUnavailable(f'HTTP {response.status_code}')
        return response

    def reserve(self, account_id: str, request_id: str, action: str, alias: str, lines: list[dict]) -> dict:
        r = self._send('POST', '/v1/reservations', json=dict(account_id=account_id, request_id=request_id, action=action,
                                                              alias=alias, lines=lines))
        if r.status_code == 402:
            b = r.json()
            raise CreditsRequired(b['balance_micros'], b['required_micros'], b['premium_requires_purchase'])
        if r.status_code == 403:
            raise AccountClosed(account_id)
        if r.status_code == 422:
            raise UnpricedModel(alias)
        if r.status_code != 201:
            raise BillingUnavailable(f'HTTP {r.status_code}')
        return r.json()

    def settle(self, request_id: str, usage: list[dict]) -> dict:
        r = self._send('POST', f'/v1/reservations/{request_id}/settle', json=dict(usage=usage))
        if r.status_code == 404:
            raise ReservationMissing(request_id)
        if r.status_code != 200:
            raise BillingUnavailable(f'HTTP {r.status_code}')
        return r.json()

    def release(self, request_id: str) -> None:
        self._send('POST', f'/v1/reservations/{request_id}/release')

    def balance(self, account_id: str) -> dict:
        r = self._send('GET', f'/v1/accounts/{account_id}/balance')
        if r.status_code != 200:
            raise BillingUnavailable(f'HTTP {r.status_code}')
        return r.json()

    def estimate(self, alias: str, input_tokens: int, output_tokens: int) -> int:
        r = self._send('POST', '/v1/estimate', json=dict(alias=alias, input_tokens=input_tokens, output_tokens=output_tokens))
        if r.status_code == 422:
            raise UnpricedModel(alias)
        return r.json()['micros']

    def packs(self, channel: str = 'web') -> list[dict]:
        r = self._send('GET', '/v1/packs', params={'channel': channel})
        if r.status_code != 200:
            raise BillingUnavailable(f'HTTP {r.status_code}')
        return r.json()['packs']

    def checkout(self, account_id: str, pack: str) -> tuple[int, dict]:
        """Returns (status, body) so the caller can explain refusals precisely."""
        try:
            r = self.http.request('POST', '/v1/checkout', json=dict(account_id=account_id, pack=pack))
        except httpx.HTTPError as exc:
            raise BillingUnavailable(type(exc).__name__) from exc
        # 502/503 here are billing's own answers about the payment provider, not a billing outage.
        if r.status_code not in (200, 403, 422, 502, 503):
            raise BillingUnavailable(f'HTTP {r.status_code}')
        return r.status_code, r.json()

    def history(self, account_id: str, before_id: int | None = None, limit: int = 50) -> dict:
        params = {'limit': limit} | ({'before_id': before_id} if before_id else {})
        r = self._send('GET', f'/v1/accounts/{account_id}/history', params=params)
        if r.status_code != 200:
            raise BillingUnavailable(f'HTTP {r.status_code}')
        return r.json()

    def close_account(self, account_id: str) -> None:
        r = self._send('POST', f'/v1/accounts/{account_id}/close')
        if r.status_code != 204:
            raise BillingUnavailable(f'HTTP {r.status_code}')

    def grant_starter(self, account_id: str, email: str | None = None, email_verified: bool = False) -> dict:
        r = self._send('POST', f'/v1/accounts/{account_id}/grants/starter', json=dict(email=email, email_verified=email_verified))
        return r.json() if r.status_code == 200 else {'granted': False, 'reason': 'unknown'}


@lru_cache
def _cached(base_url: str, token: str) -> BillingClient:
    return BillingClient(base_url, token)


def get_client() -> BillingClient:
    s = get_base_settings()
    return _cached(s.billing_base_url, s.billing_service_token.get_secret_value())
