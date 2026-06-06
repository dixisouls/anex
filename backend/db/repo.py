"""
Repository: async query helpers over the ORM models.

This is the only place that talks to Postgres. Callers pass an AsyncSession (from
session_scope or the FastAPI dependency). Agent helpers convert to and from the
Pydantic contract Agent so the rest of the code keeps speaking the contract shape
and never imports the ORM model directly.

Task, subtask, and ledger writes will grow here as B2 and B3 need them; the
models already exist so the schema is migrated ahead of the code that uses it.
"""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from contracts.schemas import Agent as AgentSchema
from backend.db.models import Agent, LedgerEntry, Subtask, Task, User


# ----- agents -----

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
        price=float(a.price),
        hires=a.hires,
        wins=a.wins,
        service_url=a.service_url,
    )


async def upsert_agent(session, agent: AgentSchema) -> None:
    """Insert or update an agent by primary key (Postgres ON CONFLICT)."""
    values = dict(
        agent_id=agent.agent_id,
        name=agent.name,
        skills=agent.skills,
        capability_text=agent.capability_text,
        model=agent.model,
        tools=agent.tools,
        price=agent.price,
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


async def list_agents(session) -> list[AgentSchema]:
    res = await session.execute(select(Agent).order_by(Agent.agent_id))
    return [_to_schema(a) for a in res.scalars().all()]


async def clear_market(session) -> None:
    """Wipe the live market for a clean demo reseed. FK-safe order. Leaves users."""
    await session.execute(delete(LedgerEntry))
    await session.execute(delete(Subtask))
    await session.execute(delete(Task))
    await session.execute(delete(Agent))


# ----- users (model + ownership now; login lands later) -----

async def create_user(session, email: str, name: str, password_hash: str | None = None) -> User:
    user = User(email=email, name=name, password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def get_user_by_email(session, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()