"""Versioned prices and the charge formula. All arithmetic is Decimal; results are integer micros."""
import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import yaml

SEED = Path(__file__).parent / 'prices.seed.yaml'
TIERS = ('open', 'premium')


class UnknownAlias(KeyError):
    """No price exists for this alias: refuse to guess a charge."""


@dataclass(frozen=True)
class Price:
    alias: str
    tier: str
    input_per_m: Decimal       # USD per 1M tokens == micro-dollars per token
    output_per_m: Decimal
    cache_read_per_m: Decimal
    multiplier: Decimal
    version: int


@dataclass(frozen=True)
class Usage:
    alias: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0


def charge_micros(usage: Usage, price: Price) -> int:
    if min(usage.input_tokens, usage.output_tokens, usage.cache_read_tokens) < 0:
        raise ValueError('token counts cannot be negative')
    cost = (usage.input_tokens * price.input_per_m + usage.output_tokens * price.output_per_m
            + usage.cache_read_tokens * price.cache_read_per_m)
    return int((cost * price.multiplier).to_integral_value(rounding=ROUND_CEILING))


def provider_cost_micros(usage: Usage, price: Price) -> int:
    """What the provider charges us (no multiplier), rounded up. charge - cost is the margin."""
    cost = (usage.input_tokens * price.input_per_m + usage.output_tokens * price.output_per_m
            + usage.cache_read_tokens * price.cache_read_per_m)
    return int(cost.to_integral_value(rounding=ROUND_CEILING))


def ceiling_micros(price: Price, input_tokens: int, output_tokens: int) -> int:
    """Worst-case charge for one call, used to size a reservation."""
    return charge_micros(Usage(price.alias, input_tokens, output_tokens), price)


def price_for(prices: dict[str, Price], alias: str) -> Price:
    try:
        return prices[alias]
    except KeyError:
        raise UnknownAlias(alias) from None


def total_charge(usages: list[Usage], prices: dict[str, Price]) -> int:
    return sum(charge_micros(u, price_for(prices, u.alias)) for u in usages)


def _row_to_price(row: dict) -> Price:
    return Price(row['alias'], row['tier'], row['input_per_m'], row['output_per_m'], row['cache_read_per_m'],
                 row['multiplier'], row['version'])


def current_prices(conn) -> dict[str, Price]:
    rows = conn.execute('SELECT * FROM billing.prices WHERE version = (SELECT max(version) FROM billing.prices)').fetchall()
    return {r['alias']: _row_to_price(r) for r in rows}


def _validate(row: dict) -> dict:
    clean = dict(alias=str(row['alias']), tier=row['tier'], input_per_m=Decimal(str(row['input_per_m'])),
                 output_per_m=Decimal(str(row['output_per_m'])), cache_read_per_m=Decimal(str(row.get('cache_read_per_m', 0))),
                 multiplier=Decimal(str(row['multiplier'])))
    if clean['tier'] not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}")
    if min(clean['input_per_m'], clean['output_per_m'], clean['cache_read_per_m']) < 0:
        raise ValueError('prices cannot be negative')
    if clean['multiplier'] < 1:
        raise ValueError('multiplier cannot be below 1 (that would sell below cost)')
    return clean


def publish_prices(conn, rows: list[dict]) -> int:
    """Publish a new version. Aliases not mentioned carry over unchanged. Returns the version."""
    changes = {r['alias']: _validate(r) for r in map(dict, rows)}
    if not changes:
        raise ValueError('nothing to publish')
    conn.execute('LOCK TABLE billing.prices IN EXCLUSIVE MODE')
    latest = current_prices(conn)
    version = max((p.version for p in latest.values()), default=0) + 1
    merged = {a: dict(alias=a, tier=p.tier, input_per_m=p.input_per_m, output_per_m=p.output_per_m,
                      cache_read_per_m=p.cache_read_per_m, multiplier=p.multiplier) for a, p in latest.items()} | changes
    for row in merged.values():
        conn.execute('INSERT INTO billing.prices (version, alias, tier, input_per_m, output_per_m, cache_read_per_m, multiplier) '
                     'VALUES (%(version)s, %(alias)s, %(tier)s, %(input_per_m)s, %(output_per_m)s, %(cache_read_per_m)s, %(multiplier)s)',
                     row | {'version': version})
    return version


def seed_if_empty(conn) -> bool:
    if conn.execute('SELECT 1 FROM billing.prices LIMIT 1').fetchone():
        return False
    publish_prices(conn, yaml.safe_load(SEED.read_text()))
    return True
