"""
Wipe Postgres + Redis and re-seed a blank market (IPO prices, default agent reps).

    WEAVE_DISABLED=1 EMBEDDINGS_FAKE=1 python -m backend.tools.reset_fresh

Or: ./scripts/reset_fresh.sh
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete

from backend.db import repo
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
from backend.infra.db import session_scope
from backend.infra.redis_client import close_redis, get_redis
from backend.market import registry, seeder


async def wipe_all() -> None:
    """Delete every user and all market rows, then reset Redis."""
    r = get_redis()
    await registry.reset_redis(r)

    async with session_scope() as session:
        await session.execute(delete(LedgerEntry))
        await session.execute(delete(Subtask))
        await session.execute(delete(Task))
        await session.execute(delete(Trade))
        await session.execute(delete(Holding))
        await session.execute(delete(Agent))
        await session.execute(delete(ModelORM))
        await session.execute(delete(User))

    await registry.create_index(r)


async def reset_fresh() -> dict[str, int]:
    await wipe_all()
    counts = await seeder.seed()
    return counts


async def _main() -> None:
    counts = await reset_fresh()
    print("Fresh market ready.")
    print(
        f"  agents={counts['agents']}  models={counts['models']}  "
        f"sim_users={counts['users']}"
    )
    print()
    print("Clear browser session (paste in DevTools console, then reload):")
    print("  localStorage.removeItem('anex.user.v1');")
    print("  localStorage.removeItem('anex.brokerModel');")
    print("  localStorage.removeItem('anex.preferredTier');")
    print("  location.reload();")
    await close_redis()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
