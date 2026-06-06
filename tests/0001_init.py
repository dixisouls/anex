"""
Smoke test (async). Run against live Postgres and Redis to prove the durable
write, the Redis projection, the vector search, and the emit helper all work end
to end.

    docker compose up -d postgres redis
    pip install -r requirements.txt
    alembic upgrade head
    python -m tests.smoke_test

With EMBED_BACKEND=local (the default) this needs no GCP.
"""

import asyncio

from contracts.events import TaskScored
from backend.db import repo
from backend.infra.db import session_scope
from backend.infra.embeddings import embed_bytes
from backend.infra.redis_client import close_redis, get_redis
from backend.market.feed import emit, read_new
from backend.market.registry import leaderboard, search
from backend.market.seeder import seed


async def main() -> None:
    count = await seed()
    print(f"seeded {count} agents")

    async with session_scope() as session:
        durable = await repo.list_agents(session)
    print(f"Postgres has {len(durable)} agents (source of truth): "
          f"{sorted(a.agent_id for a in durable)}")

    r = get_redis()

    query = "write a marketing blog post announcing a product"
    print(f"\nKNN (Redis projection) for: {query!r}")
    for agent_id, match in await search(r, embed_bytes(query), k=4):
        print(f"  {agent_id:<16} match={match:.3f}")

    print("\nleaderboard (all start equal at 0.5):")
    for agent_id, rep in await leaderboard(r):
        print(f"  {agent_id:<16} reputation={rep:.3f}")

    print("\nemit and read back one event:")
    entry_id = await emit(r, TaskScored(subtask_id="s-001", agent_id="writer-01", judge_score=0.86))
    print(f"  emitted entry {entry_id}")
    for eid, event in await read_new(r, last_id="0-0"):
        print(f"  read entry {eid}: type={event.type} agent={event.agent_id} score={event.judge_score}")

    await close_redis()
    print("\nsmoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())