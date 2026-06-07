"""
Seeder (async). Lists model stocks, seed agents, and sim users; projects to Redis.

    python -m backend.market.seeder
"""

import asyncio

from backend.config import SIM_INVESTORS, SIM_POSTERS, USER_START_CREDITS
from backend.db import repo
from backend.infra.db import session_scope
from backend.ports.factory import get_embeddings
from backend.infra.redis_client import close_redis, get_redis
from backend.market import exchange, registry
from backend.market.capabilities import PRIMARY_TIER_BY_CAPABILITY
from backend.market.registry import is_search_index_primary
from backend.market.seed_agents import SEED_AGENTS
from backend.market.seed_models import SEED_MODELS


async def seed() -> dict[str, int]:
    """Fresh market. Returns counts {agents, models, users}."""
    r = get_redis()
    await registry.reset_redis(r)
    await registry.create_index(r)

    async with session_scope() as session:
        await repo.clear_market(session)

        for spec in SEED_MODELS:
            await exchange.list_model(
                session,
                r,
                model_id=spec["model_id"],
                name=spec["name"],
                provider=spec["provider"],
                tier=spec["tier"],
            )

        for agent in SEED_AGENTS:
            await repo.upsert_agent(session, agent)

        user_count = 0
        for i in range(1, SIM_POSTERS + 1):
            await repo.create_user(
                session,
                email=f"sim-poster-{i}@bazaar.local",
                name=f"sim-poster-{i}",
                credits=USER_START_CREDITS,
                is_sim=True,
            )
            user_count += 1
        for i in range(1, SIM_INVESTORS + 1):
            await repo.create_user(
                session,
                email=f"sim-investor-{i}@bazaar.local",
                name=f"sim-investor-{i}",
                credits=USER_START_CREDITS,
                is_sim=True,
            )
            user_count += 1

    emb = get_embeddings()
    for agent in SEED_AGENTS:
        if is_search_index_primary(agent, PRIMARY_TIER_BY_CAPABILITY):
            vector = emb.embed_bytes(registry.agent_embed_text(agent))
        else:
            vector = None
        await registry.project_agent(r, agent, vector)

    return {"agents": len(SEED_AGENTS), "models": len(SEED_MODELS), "users": user_count}


async def _main() -> None:
    counts = await seed()
    print(
        f"Seeded {counts['agents']} agents, {counts['models']} models, "
        f"{counts['users']} sim users into Postgres and projected to Redis"
    )
    await close_redis()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
