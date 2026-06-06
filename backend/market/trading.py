"""Trade orchestration: AMM + user credits + holdings in one session."""

import uuid

import weave

from contracts.events import PortfolioChanged, TradeExecuted
from backend.db import repo
from backend.market import exchange, portfolio
from backend.ports.factory import get_event_bus

bus = get_event_bus()


@weave.op
async def trade(session, r, *, user_id, model_id, side, amount) -> dict:
    """BUY: amount = credits to spend. SELL: amount = shares to sell."""
    user = await repo.get_user(session, user_id)
    if side == "buy":
        if amount <= 0 or float(user.credits) < amount:
            raise ValueError("insufficient credits")
        shares_out, price = await exchange.buy(session, r, model_id=model_id, dc=amount)
        await repo.adjust_user_credits(session, user_id, -amount)
        await repo.upsert_holding_delta(session, user_id, model_id, +shares_out)
        spent, got = amount, shares_out
    elif side == "sell":
        h = await repo.get_holding(session, user_id, model_id)
        if h is None or amount <= 0 or float(h.shares) < amount:
            raise ValueError("insufficient shares")
        credits_out, price = await exchange.sell(session, r, model_id=model_id, ds=amount)
        await repo.adjust_user_credits(session, user_id, +credits_out)
        await repo.upsert_holding_delta(session, user_id, model_id, -amount)
        spent, got = amount, credits_out
    else:
        raise ValueError("side must be buy|sell")
    trade_id = uuid.uuid4().hex
    await repo.record_trade(
        session,
        user_id=user_id,
        model_id=model_id,
        side=side,
        shares=(got if side == "buy" else amount),
        credits=(spent if side == "buy" else got),
        price=price,
    )
    await bus.publish(
        TradeExecuted(
            trade_id=trade_id,
            user_id=str(user_id),
            model_id=model_id,
            side=side,
            shares=(got if side == "buy" else amount),
            credits=(spent if side == "buy" else got),
            price=price,
        )
    )
    p = await portfolio.value(session, r, user_id)
    await bus.publish(
        PortfolioChanged(
            user_id=str(user_id),
            credits=p.credits,
            holdings_value=p.holdings_value,
            total=p.total,
        )
    )
    return {
        "trade_id": trade_id,
        "price": price,
        "shares": (got if side == "buy" else amount),
        "credits": (spent if side == "buy" else got),
    }
