"""
Repository: async query helpers over the ORM models.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from contracts.schemas import Agent as AgentSchema
from backend.db.models import (
    Agent,
    Holding,
    LedgerEntry,
    Model as ModelORM,
    Subtask,
    Task,
    Trade,
    User,
)


def _to_schema(a: Agent) -> AgentSchema:
    return AgentSchema(
        agent_id=a.agent_id,
        name=a.name,
        skills=list(a.skills or []),
        capability_text=a.capability_text,
        model=a.model,
        tools=list(a.tools or []),
        reputation=float(a.reputation),
        credits=float(a.credits),
        margin=float(a.margin),
        hires=a.hires,
        wins=a.wins,
        service_url=a.service_url,
    )


async def upsert_agent(session, agent: AgentSchema) -> None:
    values = dict(
        agent_id=agent.agent_id,
        name=agent.name,
        skills=agent.skills,
        capability_text=agent.capability_text,
        model=agent.model,
        tools=agent.tools,
        margin=agent.margin,
        reputation=agent.reputation,
        credits=agent.credits,
        hires=agent.hires,
        wins=agent.wins,
        service_url=agent.service_url,
    )
    stmt = pg_insert(Agent).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Agent.agent_id],
        set_={k: v for k, v in values.items() if k != "agent_id"},
    )
    await session.execute(stmt)


async def get_agent(session, agent_id: str) -> AgentSchema | None:
    a = await session.get(Agent, agent_id)
    return _to_schema(a) if a else None


async def update_agent_stats(
    session,
    agent_id: str,
    *,
    reputation: float,
    credits: float,
    inc_hires: int = 0,
    inc_wins: int = 0,
) -> None:
    a = await session.get(Agent, agent_id)
    if a is None:
        raise KeyError(agent_id)
    a.reputation = reputation
    a.credits = credits
    a.hires += inc_hires
    a.wins += inc_wins


async def add_ledger_entry(
    session,
    *,
    agent_id: str,
    task_id: str | uuid.UUID | None,
    kind: str,
    credits_delta: float,
    reputation_before: float | None = None,
    reputation_after: float | None = None,
    model_id: str | None = None,
    amount: float | None = None,
) -> LedgerEntry:
    task_uuid = None
    if task_id is not None:
        task_uuid = task_id if isinstance(task_id, uuid.UUID) else uuid.UUID(str(task_id))
    entry = LedgerEntry(
        agent_id=agent_id,
        task_id=task_uuid,
        kind=kind,
        credits_delta=credits_delta,
        reputation_before=reputation_before,
        reputation_after=reputation_after,
        model_id=model_id,
        amount=amount,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_agents(session) -> list[AgentSchema]:
    res = await session.execute(select(Agent).order_by(Agent.agent_id))
    return [_to_schema(a) for a in res.scalars().all()]


async def clear_market(session) -> None:
    """Wipe market tables. Removes sim users; leaves non-sim users."""
    await session.execute(delete(LedgerEntry))
    await session.execute(delete(Subtask))
    await session.execute(delete(Task))
    await session.execute(delete(Trade))
    await session.execute(delete(Holding))
    await session.execute(delete(Agent))
    await session.execute(delete(ModelORM))
    await session.execute(delete(User).where(User.is_sim.is_(True)))


# ----- models -----


async def upsert_model(
    session,
    *,
    model_id: str,
    name: str,
    provider: str,
    tier: str,
    shares: float,
    credits: float,
    ipo_price: float,
    executable: bool = True,
) -> ModelORM:
    values = dict(
        model_id=model_id,
        name=name,
        provider=provider,
        tier=tier,
        executable=executable,
        pool_shares=shares,
        pool_credits=credits,
        ipo_price=ipo_price,
    )
    stmt = pg_insert(ModelORM).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ModelORM.model_id],
        set_={k: v for k, v in values.items() if k != "model_id"},
    )
    await session.execute(stmt)
    await session.flush()
    m = await session.get(ModelORM, model_id)
    if m is None:
        raise KeyError(model_id)
    return m


async def get_model(session, model_id: str) -> ModelORM | None:
    return await session.get(ModelORM, model_id)


async def list_models(session) -> list[ModelORM]:
    res = await session.execute(select(ModelORM).order_by(ModelORM.model_id))
    return list(res.scalars().all())


async def update_model_pool(
    session, model_id: str, *, shares: float, credits: float
) -> None:
    m = await session.get(ModelORM, model_id)
    if m is None:
        raise KeyError(model_id)
    m.pool_shares = shares
    m.pool_credits = credits


# ----- users -----


async def create_user(
    session,
    email: str,
    name: str,
    *,
    credits: float = 0.0,
    is_sim: bool = False,
    password_hash: str | None = None,
) -> User:
    user = User(
        email=email,
        name=name,
        credits=credits,
        is_sim=is_sim,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_email(session, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def list_users(session) -> list[User]:
    res = await session.execute(select(User).order_by(User.email))
    return list(res.scalars().all())


async def adjust_user_credits(session, user_id, delta: float) -> float:
    user = await session.get(User, user_id)
    if user is None:
        raise KeyError(user_id)
    user.credits = float(user.credits) + delta
    return float(user.credits)


# ----- holdings / trades -----


async def get_holding(session, user_id, model_id: str) -> Holding | None:
    res = await session.execute(
        select(Holding).where(Holding.user_id == user_id, Holding.model_id == model_id)
    )
    return res.scalar_one_or_none()


async def upsert_holding(session, user_id, model_id: str, shares: float) -> None:
    existing = await get_holding(session, user_id, model_id)
    if existing is None:
        session.add(Holding(user_id=user_id, model_id=model_id, shares=shares))
    else:
        existing.shares = shares
    await session.flush()


async def list_holdings(session, user_id) -> list[Holding]:
    res = await session.execute(select(Holding).where(Holding.user_id == user_id))
    return list(res.scalars().all())


async def record_trade(
    session,
    *,
    user_id,
    model_id: str,
    side: str,
    shares: float,
    credits: float,
    price: float,
) -> Trade:
    trade = Trade(
        user_id=user_id,
        model_id=model_id,
        side=side,
        shares=shares,
        credits=credits,
        price=price,
    )
    session.add(trade)
    await session.flush()
    return trade


# ----- tasks / subtasks -----


def _parse_subtask_id(subtask_id: str) -> tuple[uuid.UUID, int]:
    sep = subtask_id.rfind("-")
    if sep < 0:
        raise ValueError(f"invalid subtask_id: {subtask_id!r}")
    return uuid.UUID(subtask_id[:sep]), int(subtask_id[sep + 1 :])


async def create_task(session, *, goal: str, user_id: uuid.UUID | None = None) -> Task:
    task = Task(goal=goal, user_id=user_id, status="running")
    session.add(task)
    await session.flush()
    return task


async def create_subtask(
    session, *, task_id: uuid.UUID, order_index: int, text: str
) -> Subtask:
    subtask = Subtask(task_id=task_id, order_index=order_index, text=text)
    session.add(subtask)
    await session.flush()
    return subtask


async def get_subtask(session, subtask_id: str) -> Subtask | None:
    task_id, order_index = _parse_subtask_id(subtask_id)
    res = await session.execute(
        select(Subtask).where(
            Subtask.task_id == task_id,
            Subtask.order_index == order_index,
        )
    )
    return res.scalar_one_or_none()


async def save_subtask_result(
    session,
    *,
    subtask_id: str,
    agent_id: str,
    output_preview: str,
    judge_score: float,
) -> None:
    subtask = await get_subtask(session, subtask_id)
    if subtask is None:
        return
    subtask.assigned_agent_id = agent_id
    subtask.output_preview = output_preview
    subtask.judge_score = judge_score
