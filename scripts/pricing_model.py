"""Unit economics for the hosted pay-per-use design (specs/2026-11-17-hosted-product-design.md).

Deterministic source for every price table in that spec. Run:
    python scripts/pricing_model.py
Prices are USD per million tokens; amounts are integer micro-dollars to avoid float drift.
"""
from __future__ import annotations

import math

MICROS = 1_000_000
CREDIT_MICROS = 1_000  # 1 credit = $0.001

# Indicative OpenRouter list prices, Nov 2026: (input, output) USD per 1M tokens.
MODELS = {
    "Qwen3-14B": (0.12, 0.24),
    "GLM-4.6": (0.43, 1.75),
    "Qwen3-235B-A22B": (0.23, 2.30),
}
GUARD = MODELS["Qwen3-14B"]
OPEN_MULTIPLIER = 1.5
PREMIUM_MULTIPLIER = 1.25

# action: (main input, main output, guard input across 3 passes, guard output)
ACTIONS = {
    "chat turn": (5_000, 700, 7_000, 60),
    "10-question quiz": (8_000, 2_500, 12_000, 80),
    "coach exam grading": (6_000, 1_500, 9_000, 60),
}

FIXED_MONTHLY = 30 + 99 / 12 + 5  # VPS, Apple developer fee, domain + backups
BLENDED_PAYMENT_FEE = 0.10


def cost_micros(tokens_in: int, tokens_out: int, price: tuple[float, float]) -> int:
    """Provider cost in micro-dollars, rounded up so we never under-charge."""
    return math.ceil(tokens_in * price[0] + tokens_out * price[1])


def charge_micros(provider_cost: int, multiplier: float) -> int:
    return math.ceil(provider_cost * multiplier)


def action_charge_credits(model: str, action: str, multiplier: float = OPEN_MULTIPLIER) -> float:
    i, o, gi, go = ACTIONS[action]
    cost = cost_micros(i, o, MODELS[model]) + cost_micros(gi, go, GUARD)
    return charge_micros(cost, multiplier) / CREDIT_MICROS


def mor_net(gross: float, pct: float = 0.05, fixed: float = 0.50) -> float:
    return gross - (gross * pct + fixed)


def monthly_net(user_spend: float, multiplier: float = OPEN_MULTIPLIER) -> float:
    margin = user_spend * (1 - 1 / multiplier)
    return margin - user_spend * BLENDED_PAYMENT_FEE - FIXED_MONTHLY


def break_even(multiplier: float = OPEN_MULTIPLIER) -> float:
    return FIXED_MONTHLY / ((1 - 1 / multiplier) - BLENDED_PAYMENT_FEE)


def main() -> None:
    print("Credits per action (open multiplier 1.5x, guard on Qwen3-14B)")
    for model in MODELS:
        row = "  ".join(f"{a}: {action_charge_credits(model, a):.1f}" for a in ACTIONS)
        print(f"  {model:16} {row}")
    print("\nWeb top-up net (merchant of record 5% + $0.50) vs store 15%")
    for amount in (5, 10, 20, 50):
        print(f"  ${amount:>3}: MoR ${mor_net(amount):6.2f}  store ${amount * 0.85:6.2f}")
    print("\nMonthly net after model cost, fees and fixed costs")
    for spend in (100, 250, 500, 1000):
        print(f"  ${spend:>5}: ${monthly_net(spend):8.2f}")
    print(f"\nBreak-even monthly top-ups: ${break_even():.0f}")


if __name__ == "__main__":
    main()
