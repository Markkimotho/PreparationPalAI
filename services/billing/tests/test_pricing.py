from decimal import Decimal

import pytest

from billing.pricing import (Price, UnknownAlias, Usage, ceiling_micros, charge_micros, current_prices,
                             price_for, publish_prices, seed_if_empty, total_charge)


@pytest.fixture
def prices(conn):
    seed_if_empty(conn)
    return current_prices(conn)


def test_seed_loads_every_gateway_alias_once(conn):
    assert seed_if_empty(conn) is True
    assert seed_if_empty(conn) is False
    assert set(current_prices(conn)) == {'open-default', 'open-fast', 'open-reasoning', 'guard', 'vision-open',
                                         'embed-default', 'premium-claude', 'premium-gpt', 'premium-grok'}


def test_quiz_with_guard_matches_hand_calculation(prices):
    # open-default: (8000 x 0.40 + 2500 x 1.75) x 1.5 = 11362.5 -> 11363
    # guard:        (12000 x 0.12 + 80 x 0.24) x 1.5 = 2188.8   -> 2189
    main = charge_micros(Usage('open-default', 8000, 2500), prices['open-default'])
    guard = charge_micros(Usage('guard', 12000, 80), prices['guard'])
    assert (main, guard) == (11363, 2189)
    assert total_charge([Usage('open-default', 8000, 2500), Usage('guard', 12000, 80)], prices) == 13552


def test_rounds_up_and_a_used_token_is_never_free(prices):
    assert charge_micros(Usage('guard', 1, 0), prices['guard']) == 1
    assert charge_micros(Usage('guard', 0, 0), prices['guard']) == 0


def test_premium_uses_the_premium_multiplier(prices):
    # (1000 x 2.00 + 1000 x 10.00) x 1.25 = 15000
    assert charge_micros(Usage('premium-claude', 1000, 1000), prices['premium-claude']) == 15000
    assert prices['premium-claude'].tier == 'premium'


def test_cache_read_tokens_use_their_own_rate():
    price = Price('x', 'open', Decimal('1'), Decimal('2'), Decimal('0.1'), Decimal('1.5'), 1)
    assert charge_micros(Usage('x', 100, 10, cache_read_tokens=1000), price) == 330  # (100 x 1 + 10 x 2 + 1000 x 0.1) x 1.5


def test_unknown_alias_is_rejected_not_free(prices):
    with pytest.raises(UnknownAlias):
        price_for(prices, 'qwen2.5:7b')
    with pytest.raises(UnknownAlias):
        total_charge([Usage('qwen2.5:7b', 10, 10)], prices)


def test_negative_token_counts_are_rejected(prices):
    with pytest.raises(ValueError):
        charge_micros(Usage('guard', -1, 0), prices['guard'])


def test_ceiling_is_the_charge_for_the_worst_case(prices):
    assert ceiling_micros(prices['open-default'], 5000, 2048) == charge_micros(Usage('open-default', 5000, 2048), prices['open-default'])


def test_publishing_creates_a_new_version_and_old_prices_stay_readable(conn):
    seed_if_empty(conn)
    old = current_prices(conn)
    version = publish_prices(conn, [dict(alias='open-default', tier='open', input_per_m='0.80', output_per_m='3.50', multiplier='1.5')])
    new = current_prices(conn)
    assert version == old['open-default'].version + 1 and new['open-default'].version == version
    assert new['open-default'].input_per_m == Decimal('0.80')
    assert set(new) == set(old)  # aliases not mentioned carry over to the new version
    assert charge_micros(Usage('open-default', 1000, 0), old['open-default']) == 600
    assert charge_micros(Usage('open-default', 1000, 0), new['open-default']) == 1200


@pytest.mark.parametrize('bad', [dict(multiplier='0.9'), dict(input_per_m='-1'), dict(tier='gold')])
def test_publish_validates_rows(conn, bad):
    seed_if_empty(conn)
    row = dict(alias='guard', tier='open', input_per_m='0.12', output_per_m='0.24', multiplier='1.5') | bad
    with pytest.raises(ValueError):
        publish_prices(conn, [row])
