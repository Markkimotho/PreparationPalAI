"""The model aliases the gateway serves to this app, cached briefly."""
import threading
import time

import httpx

from app.config import get_settings

TTL = 30.0
_lock = threading.Lock()
_cache: dict = {'at': None, 'ids': set(), 'key': None}
ORDER = ['open-default', 'open-fast', 'open-reasoning', 'premium-claude', 'premium-gpt', 'premium-grok']


def clear_cache() -> None:
    with _lock:
        _cache.update(at=None, ids=set(), key=None)


def all_ids() -> set[str]:
    """Every alias the app's key can use. Empty when the gateway is unreachable (never cached)."""
    settings = get_settings()
    key = (settings.gateway_base_url, settings.gateway_api_key.get_secret_value())
    with _lock:
        if _cache['at'] is not None and _cache['key'] == key and time.monotonic() - _cache['at'] < TTL:
            return set(_cache['ids'])
    try:
        response = httpx.get(f'{settings.gateway_base_url.rstrip("/")}/v1/models', timeout=5,
                             headers={'Authorization': f'Bearer {key[1]}'})
        response.raise_for_status()
        ids = {m['id'] for m in response.json()['data']}
    except (httpx.HTTPError, ValueError, KeyError):
        return set()
    with _lock:
        _cache.update(at=time.monotonic(), ids=ids, key=key)
    return set(ids)


def tier_of(alias: str) -> str | None:
    return 'premium' if alias.startswith('premium-') else 'open' if alias.startswith('open-') else None


def selectable() -> set[str]:
    """Aliases a learner may pick. Guard, vision, embedding and fallback aliases stay internal."""
    return {a for a in all_ids() if tier_of(a) and not a.endswith('-fallback')}


def ordered(ids: set[str]) -> list[str]:
    return [a for a in ORDER if a in ids] + sorted(ids - set(ORDER))


def healthy() -> bool:
    try:
        httpx.get(f'{get_settings().gateway_base_url.rstrip("/")}/health/liveliness', timeout=3).raise_for_status()
        return True
    except httpx.HTTPError:
        return False
