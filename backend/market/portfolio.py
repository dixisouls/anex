"""Portfolio valuation: cash + marked-to-market holdings."""

from contracts.schemas import Holding, Portfolio
from backend.db import repo
from backend.market import registry


async def value(session, r, user_id) -> Portfolio:
    user = await repo.get_user(session, user_id)
    holdings = await repo.list_holdings(session, user_id)
    items, hv = [], 0.0
    for h in holdings:
        price = await registry.get_model_price(r, h.model_id) or 0.0
        val = float(h.shares) * price
        hv += val
        items.append(
            Holding(
                model_id=h.model_id,
                shares=float(h.shares),
                price=price,
                value=val,
            )
        )
    credits = float(user.credits)
    return Portfolio(
        user_id=str(user_id),
        credits=credits,
        holdings=items,
        holdings_value=hv,
        total=credits + hv,
    )
