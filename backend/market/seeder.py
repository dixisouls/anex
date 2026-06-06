"""
Seeder (async). Lists model stocks, seed agents, and sim users; projects to Redis.

    python -m backend.market.seeder
"""

import asyncio

from contracts.events import ModelListed
from backend.config import IPO_SHARES, SIM_INVESTORS, SIM_POSTERS, TIER_IPO_PRICE, USER_START_CREDITS
from backend.db import repo
from backend.infra.db import session_scope
from backend.ports.factory import get_embeddings
from backend.infra.redis_client import close_redis, get_redis
from backend.market import registry
from backend.market.feed import emit
from backend.market.seed_agents import SEED_AGENTS
from backend.market.seed_models import SEED_MODELS


async def seed() -> dict[str, int]:
    """Fresh market. Returns counts {agents, models, users}."""
    async with session_scope() as session:
        await repo.clear_market(session)

        for spec in SEED_MODELS:
            price0 = TIER_IPO_PRICE[spec["tier"]]
            shares = IPO_SHARES
            credits = price0 * shares
            await repo.upsert_model(
                session,
                model_id=spec["model_id"],
                name=spec["name"],
                provider=spec["provider"],
                tier=spec["tier"],
                shares=shares,
                credits=credits,
                ipo_price=price0,
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

        models = await repo.list_models(session)

    r = get_redis()
    await registry.reset_redis(r)
    await registry.create_index(r)

    for m in models:
        await registry.project_model(r, m)
        await emit(
            r,
            ModelListed(
                model_id=m.model_id,
                name=m.name,
                provider=m.provider,
                tier=m.tier,
                ipo_price=float(m.ipo_price),
            ),
        )

    emb = get_embeddings()
    for agent in SEED_AGENTS:
        await registry.project_agent(r, agent, emb.embed_bytes(agent.capability_text))

    return {"agents": len(SEED_AGENTS), "models": len(models), "users": user_count}


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
