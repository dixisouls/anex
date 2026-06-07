"""User credit grants (demo purchases, no payment gateway)."""

import weave

from contracts.events import PortfolioChanged
from backend.db import repo
from backend.infra.db import session_scope
from backend.market import portfolio
from backend.ports.factory import get_event_bus

bus = get_event_bus()

MIN_BUY_AMOUNT = 20.0
MAX_BUY_AMOUNT = 1000.0


@weave.op
async def grant_credits(r, *, user_id, amount: float) -> float:
    """Credit a user's cash balance and emit portfolio_changed."""
    async with session_scope() as session:
        await repo.adjust_user_credits(session, user_id, amount)
        p = await portfolio.value(session, r, user_id)
    await bus.publish(
        PortfolioChanged(
            user_id=str(user_id),
            credits=p.credits,
            holdings_value=p.holdings_value,
            total=p.total,
        )
    )
    return p.credits
