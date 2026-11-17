"""Gate tests for the deterministic pricing model behind the hosted-product spec."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "pricing_model", Path(__file__).resolve().parents[1] / "scripts" / "pricing_model.py")
pm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pm)


def test_cost_rounds_up_to_whole_micros():
    # 1 token at $0.12/M is 0.12 micros; billing must never round to zero.
    assert pm.cost_micros(1, 0, (0.12, 0.24)) == 1


def test_charge_applies_multiplier_and_rounds_up():
    assert pm.charge_micros(3, 1.5) == 5


@pytest.mark.parametrize("model,action,credits", [
    ("GLM-4.6", "10-question quiz", 13.9),
    ("Qwen3-14B", "chat turn", 2.4),
    ("Qwen3-235B-A22B", "coach exam grading", 8.9),
])
def test_spec_action_table(model, action, credits):
    assert pm.action_charge_credits(model, action) == pytest.approx(credits, abs=0.05)


def test_premium_multiplier_is_cheaper_per_unit_cost():
    assert pm.action_charge_credits("GLM-4.6", "chat turn", pm.PREMIUM_MULTIPLIER) < \
        pm.action_charge_credits("GLM-4.6", "chat turn")


def test_five_dollar_web_pack_nets_same_as_store():
    assert pm.mor_net(5) == pytest.approx(5 * 0.85)


def test_break_even_matches_monthly_net():
    assert pm.monthly_net(pm.break_even()) == pytest.approx(0, abs=1e-9)
    assert round(pm.break_even()) == 185
