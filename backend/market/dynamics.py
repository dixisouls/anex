"""Market microstructure: fundamentals, bid/ask quotes, OU arb kernel, GBM paths."""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from backend.config import (
    ARB_MAX_BPS,
    AWARD_FRACTION,
    AWARD_RATE,
    EARN_BASELINE,
    EARN_CLAMP,
    EARN_RATE,
    FUNDAMENTAL_SCALE,
    IPO_SHARES,
    KAPPA_BY_TIER,
    MIN_POOL_CREDITS,
    MIN_POOL_SHARES,
    POOL_PASS_THROUGH,
    QUOTE_SIZE,
    SIGMA_BY_TIER,
)


def pool_mid(shares: float, credits: float) -> float:
    return credits / shares if shares > 0 else 0.0


def pool_depth(shares: float, credits: float) -> float:
    return math.sqrt(max(shares * credits, 0.0))


def kappa_for_tier(tier: str) -> float:
    return KAPPA_BY_TIER.get(tier, KAPPA_BY_TIER["flash"])


def sigma_for_tier(tier: str) -> float:
    return SIGMA_BY_TIER.get(tier, SIGMA_BY_TIER["flash"])


def compute_raw_earnings(score: float) -> float:
    return EARN_RATE * (score - EARN_BASELINE)


def update_fundamental(fundamental: float, raw: float) -> float:
    """Log-return style fundamental move from judge-implied earnings."""
    scale = max(fundamental * IPO_SHARES * FUNDAMENTAL_SCALE, 1e-6)
    return max(1e-6, fundamental * math.exp(raw / scale))


def pool_pass_through_amount(raw: float) -> float:
    return POOL_PASS_THROUGH * raw


def cap_award(award: float, hire_price: float) -> float:
    if hire_price <= 0:
        return award
    return min(award, hire_price * AWARD_FRACTION)


def compute_award(judge_score: float, derived_price: float, hire_price: float) -> float:
    raw = AWARD_RATE * judge_score * derived_price
    return cap_award(raw, hire_price)


def quote_buy(
    shares: float, credits: float, dc: float = QUOTE_SIZE
) -> tuple[float, float]:
    """Average ask price for spending dc credits; returns (ask, post_trade_mid)."""
    mid = pool_mid(shares, credits)
    if dc <= 0 or mid <= 0:
        return mid, mid
    k = shares * credits
    c2 = credits + dc
    s2 = max(MIN_POOL_SHARES, k / c2)
    shares_out = shares - s2
    if shares_out <= 0:
        return mid, mid
    ask = dc / shares_out
    return ask, pool_mid(s2, c2)


def quote_sell(
    shares: float, credits: float, notional: float = QUOTE_SIZE
) -> tuple[float, float]:
    """Average bid price for notional credits of shares; returns (bid, post_trade_mid)."""
    mid = pool_mid(shares, credits)
    if mid <= 0 or notional <= 0:
        return mid, mid
    ds = notional / mid
    k = shares * credits
    s2 = shares + ds
    c2 = max(MIN_POOL_CREDITS, k / s2)
    credits_out = credits - c2
    if credits_out <= 0 or ds <= 0:
        return mid, mid
    bid = credits_out / ds
    return bid, pool_mid(s2, c2)


def spread_bps(bid: float, ask: float, mid: float) -> float:
    if mid <= 0 or ask < bid:
        return 0.0
    return (ask - bid) / mid * 10000.0


def arb_pool_adjustment(
    shares: float,
    credits: float,
    fundamental: float,
    tier: str,
    dt: float,
    rng: random.Random,
) -> float:
    """OU pull toward fundamental + exogenous noise, as a pool credit delta."""
    price = pool_mid(shares, credits)
    if price <= 0 or fundamental <= 0 or shares <= 0:
        return 0.0
    gap = (fundamental - price) / price
    kappa = kappa_for_tier(tier)
    sigma = sigma_for_tier(tier)
    d_log = kappa * gap * dt + sigma * math.sqrt(max(dt, 1e-9)) * rng.gauss(0.0, 1.0)
    cap = ARB_MAX_BPS / 10000.0
    d_log = max(-cap, min(cap, d_log))
    c_new = credits * math.exp(d_log)
    amount = c_new - credits
    return max(-EARN_CLAMP, min(EARN_CLAMP, amount))


def generate_gbm_path(
    ipo: float,
    target: float,
    *,
    steps: int = 120,
    tier: str,
    rng: random.Random,
) -> list[float]:
    """Geometric path from ipo toward target with drift + volatility + jumps."""
    if steps < 2:
        return [target]
    sigma = sigma_for_tier(tier) * 2.5
    total_log = math.log(max(target, 1e-6) / max(ipo, 1e-6))
    mu = total_log / (steps - 1)
    floor = ipo * 0.5
    prices = [ipo]
    for _ in range(steps - 2):
        z = rng.gauss(0.0, 1.0)
        if rng.random() < 0.06:
            z += rng.choice([-1.0, 1.0]) * rng.uniform(0.03, 0.08)
        log_r = mu + sigma * z
        prices.append(max(floor, prices[-1] * math.exp(log_r)))
    prices.append(target)
    return prices


def iso_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def vs_fair_pct(price: float, fundamental: float) -> float:
    if fundamental <= 0:
        return 0.0
    return ((price - fundamental) / fundamental) * 100.0
