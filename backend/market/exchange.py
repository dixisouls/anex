"""Constant-product AMM: list, buy, sell, inject earnings."""

import weave

from contracts.events import EarningsInjected, ModelListed, PriceChanged
from backend.config import (
    EARN_CLAMP,
    IPO_SHARES,
    MIN_POOL_CREDITS,
    MIN_POOL_SHARES,
    PRICE_HISTORY_KEY,
    TIER_IPO_PRICE,
)
from backend.db import repo
from backend.market import registry
from backend.ports.factory import get_event_bus

bus = get_event_bus()


def _price(shares: float, credits: float) -> float:
    return credits / shares


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
    await registry.project_model(r, m)
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
    S, C = float(m.pool_shares), float(m.pool_credits)
    k = S * C
    old = _price(S, C)
    C2 = C + dc
    S2 = max(MIN_POOL_SHARES, k / C2)
    shares_out = S - S2
    if shares_out <= 0:
        raise ValueError("trade too small / pool floor hit")
    await _commit_pool(session, r, model_id, S2, C2, old, reason="trade")
    return shares_out, _price(S2, C2)


@weave.op
async def sell(session, r, *, model_id, ds) -> tuple[float, float]:
    """Return ds shares, return (credits_out, new_price). Reject empty/zero."""
    m = await repo.get_model(session, model_id)
    if m is None or ds <= 0:
        raise ValueError("bad sell")
    S, C = float(m.pool_shares), float(m.pool_credits)
    k = S * C
    old = _price(S, C)
    S2 = S + ds
    C2 = max(MIN_POOL_CREDITS, k / S2)
    credits_out = C - C2
    if credits_out <= 0:
        raise ValueError("trade too small / pool floor hit")
    await _commit_pool(session, r, model_id, S2, C2, old, reason="trade")
    return credits_out, _price(S2, C2)


@weave.op
async def inject_earnings(session, r, *, model_id, agent_id, amount, judge_score):
    """Fundamentals: add credits to the pool without issuing shares."""
    m = await repo.get_model(session, model_id)
    if m is None:
        return
    S, C = float(m.pool_shares), float(m.pool_credits)
    old = _price(S, C)
    amount = max(-EARN_CLAMP, min(EARN_CLAMP, amount))
    C2 = max(MIN_POOL_CREDITS, C + amount)
    await _commit_pool(session, r, model_id, S, C2, old, reason="earnings")
    await bus.publish(
        EarningsInjected(
            model_id=model_id,
            agent_id=agent_id,
            amount=amount,
            judge_score=judge_score,
        )
    )


async def _commit_pool(session, r, model_id, S2, C2, old_price, *, reason):
    await repo.update_model_pool(session, model_id, shares=S2, credits=C2)
    m = await repo.get_model(session, model_id)
    await registry.project_model(r, m)
    new = _price(S2, C2)
    await bus.publish(
        PriceChanged(model_id=model_id, old=old_price, new=new, reason=reason)
    )
    await r.xadd(PRICE_HISTORY_KEY, {"model_id": model_id, "price": str(new)})
