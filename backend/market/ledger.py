"""Ledger: reputation EMA, credit awards, earnings handoff."""

import weave

from contracts.events import CreditsChanged, PortfolioChanged, ReputationChanged
from backend.config import AWARD_RATE, EARN_BASELINE, EARN_RATE, REP_ALPHA
from backend.db import repo
from backend.infra.db import session_scope
from backend.market import exchange, portfolio, registry
from backend.ports.factory import get_event_bus

bus = get_event_bus()


@weave.op
async def charge_hire(r, *, user_id, agent_id, price, task_id) -> None:
    """Debit the poster and pay the hired agent's treasury (credits conserved).

    Runs in its own committed transaction so the post-judge settle() (which
    happens later in a separate session) reads the updated agent treasury and
    does not clobber this write.
    """
    async with session_scope() as session:
        await repo.adjust_user_credits(session, user_id, -price)
        old_cred, new_cred = await repo.adjust_agent_credits(session, agent_id, price)
        await repo.add_ledger_entry(
            session,
            agent_id=agent_id,
            task_id=task_id,
            kind="hire",
            credits_delta=price,
        )
        await registry.reproject_agent(r, session, agent_id)
        p = await portfolio.value(session, r, user_id)
    await bus.publish(CreditsChanged(agent_id=agent_id, old=old_cred, new=new_cred))
    await bus.publish(
        PortfolioChanged(
            user_id=str(user_id),
            credits=p.credits,
            holdings_value=p.holdings_value,
            total=p.total,
        )
    )


@weave.op
async def settle(
    r,
    session,
    *,
    agent_id,
    model_id,
    judge_score,
    derived_price,
    task_id,
):
    a = await repo.get_agent(session, agent_id)
    if a is None:
        return
    old_rep = a.reputation
    new_rep = REP_ALPHA * judge_score + (1 - REP_ALPHA) * old_rep
    award = AWARD_RATE * judge_score * derived_price
    old_cred = a.credits
    new_cred = old_cred + award
    await repo.update_agent_stats(
        session,
        agent_id,
        reputation=new_rep,
        credits=new_cred,
        inc_hires=1,
        inc_wins=1 if judge_score >= 0.5 else 0,
    )
    await registry.update_leaderboard(r, agent_id, new_rep)
    await registry.reproject_agent(r, session, agent_id)
    await bus.publish(
        ReputationChanged(agent_id=agent_id, old=old_rep, new=new_rep)
    )
    await bus.publish(CreditsChanged(agent_id=agent_id, old=old_cred, new=new_cred))
    await repo.add_ledger_entry(
        session,
        agent_id=agent_id,
        task_id=task_id,
        kind="award",
        credits_delta=award,
        reputation_before=old_rep,
        reputation_after=new_rep,
    )
    hire_weight = 1.0
    earnings = EARN_RATE * (judge_score - EARN_BASELINE) * hire_weight
    await exchange.inject_earnings(
        session,
        r,
        model_id=model_id,
        agent_id=agent_id,
        amount=earnings,
        judge_score=judge_score,
    )
    await repo.add_ledger_entry(
        session,
        agent_id=agent_id,
        task_id=task_id,
        kind="earnings",
        credits_delta=0,
        model_id=model_id,
        amount=earnings,
    )
