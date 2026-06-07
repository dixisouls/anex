"""Constant-product AMM: list, buy, sell, inject earnings, arb."""

import random

import weave

from contracts.events import EarningsInjected, ModelListed, PriceChanged
from backend.config import (
    EARN_CLAMP,
    IPO_SHARES,
    MIN_POOL_CREDITS,
    MIN_POOL_SHARES,
    TIER_IPO_PRICE,
)
from backend.db import repo
from backend.market import dynamics, registry
from backend.ports.factory import get_event_bus

bus = get_event_bus()


def _price(shares: float, credits: float) -> float:
    return dynamics.pool_mid(shares, credits)


async def list_model(
    session, r, *, model_id, name, provider, tier, executable=True
):
    price0 = TIER_IPO_PRICE[tier]
    shares, credits = IPO_SHARES, price0 * IPO_SHARES
    m = await repo.upsert_model(
        session,
        model_id=model_id,
        name=name,
        provider=provider,
        tier=tier,
        shares=shares,
        credits=credits,
        ipo_price=price0,
        executable=executable,
    )
    await registry.init_market_fields(r, model_id, price0)
    await registry.project_model(r, m)
    await registry.append_price_tick(r, model_id=model_id, price=price0, reason="ipo")
    await bus.publish(
        ModelListed(
            model_id=model_id,
            name=name,
            provider=provider,
            tier=tier,
            ipo_price=price0,
        )
    )
    return m


@weave.op
async def buy(session, r, *, model_id, dc) -> tuple[float, float]:
    """Spend dc credits, return (shares_out, new_price). Reject empty/zero."""
    m = await repo.get_model(session, model_id)
    if m is None or dc <= 0:
        raise ValueError("bad buy")
    s, c = float(m.pool_shares), float(m.pool_credits)
    k = s * c
    old = _price(s, c)
    c2 = c + dc
    s2 = max(MIN_POOL_SHARES, k / c2)
    shares_out = s - s2
    if shares_out <= 0:
        raise ValueError("trade too small / pool floor hit")
    await _commit_pool(
        session, r, model_id, s2, c2, old, reason="trade", volume_delta=shares_out
    )
    return shares_out, _price(s2, c2)


@weave.op
async def sell(session, r, *, model_id, ds) -> tuple[float, float]:
    """Return ds shares, return (credits_out, new_price). Reject empty/zero."""
    m = await repo.get_model(session, model_id)
    if m is None or ds <= 0:
        raise ValueError("bad sell")
    s, c = float(m.pool_shares), float(m.pool_credits)
    k = s * c
    old = _price(s, c)
    s2 = s + ds
    c2 = max(MIN_POOL_CREDITS, k / s2)
    credits_out = c - c2
    if credits_out <= 0:
        raise ValueError("trade too small / pool floor hit")
    await _commit_pool(
        session, r, model_id, s2, c2, old, reason="trade", volume_delta=ds
    )
    return credits_out, _price(s2, c2)


@weave.op
async def inject_earnings(session, r, *, model_id, agent_id, amount, judge_score):
    """Fundamentals: add credits to the pool without issuing shares."""
    m = await repo.get_model(session, model_id)
    if m is None:
        return
    s, c = float(m.pool_shares), float(m.pool_credits)
    old = _price(s, c)
    amount = max(-EARN_CLAMP, min(EARN_CLAMP, amount))
    c2 = max(MIN_POOL_CREDITS, c + amount)
    await _commit_pool(session, r, model_id, s, c2, old, reason="earnings")
    await bus.publish(
        EarningsInjected(
            model_id=model_id,
            agent_id=agent_id,
            amount=amount,
            judge_score=judge_score,
        )
    )


async def inject_arb(
    session,
    r,
    *,
    model_id: str,
    dt: float,
    rng: random.Random | None = None,
) -> bool:
    """Mean-reverting OU adjustment toward fundamental fair value."""
    m = await repo.get_model(session, model_id)
    if m is None:
        return False
    s, c = float(m.pool_shares), float(m.pool_credits)
    old = _price(s, c)
    fundamental = await registry.get_fundamental(r, model_id, old)
    rng = rng or random.Random()
    amount = dynamics.arb_pool_adjustment(s, c, fundamental, m.tier, dt, rng)
    if abs(amount) < 1e-9:
        return False
    c2 = max(MIN_POOL_CREDITS, c + amount)
    await _commit_pool(session, r, model_id, s, c2, old, reason="arb")
    return True


async def _commit_pool(
    session,
    r,
    model_id,
    s2,
    c2,
    old_price,
    *,
    reason,
    volume_delta: float = 0.0,
):
    await repo.update_model_pool(session, model_id, shares=s2, credits=c2)
    m = await repo.get_model(session, model_id)
    new = _price(s2, c2)
    await registry.bump_session_stats(r, model_id, new, volume_delta=volume_delta)
    await registry.project_model(r, m)
    await bus.publish(
        PriceChanged(model_id=model_id, old=old_price, new=new, reason=reason)
    )
    await registry.append_price_tick(r, model_id=model_id, price=new, reason=reason)
