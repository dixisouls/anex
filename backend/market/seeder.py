"""
Seeder (async).

Loads the market: writes the seed agents to Postgres (the source of truth), then
projects each into Redis (hash plus capability vector for KNN, leaderboard score).
This is what POST /seed (B4) will call, and what you run during dev for a clean
market. Reset clears the durable tables and the Redis projection so a reseed is a
true clean slate.

Run it (after the schema is migrated with `alembic upgrade head`):
    python -m backend.market.seeder
"""

import asyncio

from backend.config import DATABASE_URL
from backend.db import repo
from backend.infra.db import session_scope
from backend.infra.embeddings import embed_bytes
from backend.infra.redis_client import close_redis, get_redis
from backend.market import registry
from backend.market.seed_agents import SEED_AGENTS


async def seed() -> int:
    """Fresh market from the seed roster. Returns the agent count.

    Order matters: Postgres first (truth), then the Redis projection, so Redis is
    never ahead of the durable record."""
    # 1. durable write
    async with session_scope() as session:
        await repo.clear_market(session)
        for agent in SEED_AGENTS:
            await repo.upsert_agent(session, agent)

    # 2. project into Redis
    r = get_redis()
    await registry.reset_redis(r)
    await registry.create_index(r)
    for agent in SEED_AGENTS:
        await registry.project_agent(r, agent, embed_bytes(agent.capability_text))

    return len(SEED_AGENTS)


async def _main() -> None:
    count = await seed()
    print(f"Seeded {count} agents into Postgres and projected to Redis")
    await close_redis()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()