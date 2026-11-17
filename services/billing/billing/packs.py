"""Credit packs sold on the web (spec 8.3). Credits come from this table, never from a payment amount."""
import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Pack:
    id: str
    usd_cents: int
    credits_micros: int


PACKS: dict[str, Pack] = {p.id: p for p in (
    Pack('web-5', 500, 5_000_000),
    Pack('web-10', 1000, 10_500_000),       # +5% over the $5 pack
    Pack('web-20', 2000, 21_500_000),       # +7.5%
    Pack('web-50', 5000, 55_000_000),       # +10%
)}


def paddle_price_ids() -> dict[str, str]:
    """Pack id -> Paddle price id, from PADDLE_PRICE_IDS (JSON). Missing packs are simply not sold."""
    try:
        mapping = json.loads(os.environ.get('PADDLE_PRICE_IDS', '') or '{}')
    except ValueError:
        return {}
    return {k: v for k, v in mapping.items() if k in PACKS and isinstance(v, str) and v.startswith('pri_')}


def pack_for_price(price_id: str) -> Pack | None:
    return next((PACKS[k] for k, v in paddle_price_ids().items() if v == price_id), None)
