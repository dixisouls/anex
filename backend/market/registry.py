"""
Registry: the Redis projection and the hiring index.

Postgres is the source of truth for agents (see backend/db). Redis holds a
projection of each agent as a hash plus its capability vector, so the hot path
(KNN hiring, reading price and service_url during a task, the leaderboard) never
needs a database round trip. The projection is rebuilt by the seeder and updated
by the ledger.

This module owns the Redis layout:
- agent:{id}   hash, the projected Agent fields plus the embedding bytes
- agents_idx   FLAT COSINE vector index over the embeddings, for KNN hiring
- leaderboard  sorted set, member agent_id scored by reputation

agent_to_mapping and mapping_to_agent are pure (no Redis) and unit testable.
Everything that touches Redis is async and takes the client first.
"""

import json

from redis.commands.search.field import VectorField
from redis.commands.search.query import Query

try:
    from redis.commands.search.index_definition import IndexDefinition, IndexType
except ImportError:  # pragma: no cover
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from contracts.schemas import Agent
from backend.config import (
    AGENT_PREFIX,
    INDEX_NAME,
    LEADERBOARD_KEY,
    STREAM_KEY,
    TASK_PREFIX,
    VECTOR_DIM,
    VECTOR_FIELD,
    VECTOR_METRIC,
)
from backend.infra.util import to_str


def agent_key(agent_id: str) -> str:
    return f"{AGENT_PREFIX}{agent_id}"


# ----- serialize and deserialize (pure, no Redis) -----

def agent_to_mapping(agent: Agent, vector_bytes: bytes) -> dict:
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "skills": json.dumps(agent.skills),
        "capability_text": agent.capability_text,
        "model": agent.model,
        "tools": json.dumps(agent.tools),
        "reputation": str(agent.reputation),
        "credits": str(agent.credits),
        "price": str(agent.price),
        "hires": str(agent.hires),
        "wins": str(agent.wins),
        "service_url": agent.service_url or "",
        VECTOR_FIELD: vector_bytes,
    }


def mapping_to_agent(mapping: dict) -> Agent:
    d = {}
    for raw_key, raw_val in mapping.items():
        key = to_str(raw_key)
        if key == VECTOR_FIELD:
            continue
        d[key] = to_str(raw_val)
    return Agent(
        agent_id=d["agent_id"],
        name=d["name"],
        skills=json.loads(d["skills"]),
        capability_text=d["capability_text"],
        model=d["model"],
        tools=json.loads(d["tools"]),
        reputation=float(d["reputation"]),
        credits=float(d["credits"]),
        price=float(d["price"]),
        hires=int(d["hires"]),
        wins=int(d["wins"]),
        service_url=(d.get("service_url") or None),
    )


# ----- index lifecycle -----

async def create_index(r) -> None:
    schema = (
        VectorField(
            VECTOR_FIELD,
            "FLAT",
            {"TYPE": "FLOAT32", "DIM": VECTOR_DIM, "DISTANCE_METRIC": VECTOR_METRIC},
        ),
    )
    definition = IndexDefinition(prefix=[AGENT_PREFIX], index_type=IndexType.HASH)
    await r.ft(INDEX_NAME).create_index(schema, definition=definition)


async def drop_index(r) -> None:
    try:
        await r.ft(INDEX_NAME).dropindex(delete_documents=False)
    except Exception:
        pass  # index did not exist


async def reset_redis(r) -> None:
    """Clear the Redis projection so a reseed is a clean slate. The durable data
    in Postgres is cleared separately by repo.clear_market."""
    await drop_index(r)
    async for key in r.scan_iter(match=f"{AGENT_PREFIX}*"):
        await r.delete(key)
    async for key in r.scan_iter(match=f"{TASK_PREFIX}*"):
        await r.delete(key)
    await r.delete(LEADERBOARD_KEY)
    await r.delete(STREAM_KEY)


# ----- projection (Postgres -> Redis) -----

async def project_agent(r, agent: Agent, vector_bytes: bytes) -> None:
    """Write the agent hash and set its leaderboard score to its reputation."""
    await r.hset(agent_key(agent.agent_id), mapping=agent_to_mapping(agent, vector_bytes))
    await r.zadd(LEADERBOARD_KEY, {agent.agent_id: agent.reputation})


async def update_leaderboard(r, agent_id: str, reputation: float) -> None:
    """Called by the ledger when reputation changes."""
    await r.zadd(LEADERBOARD_KEY, {agent_id: reputation})


# ----- hot reads (from the Redis projection) -----

async def get_agent_cached(r, agent_id: str) -> Agent | None:
    mapping = await r.hgetall(agent_key(agent_id))
    if not mapping:
        return None
    return mapping_to_agent(mapping)


async def search(r, query_vector_bytes: bytes, k: int = 5) -> list[tuple[str, float]]:
    """KNN over the capability vectors. Returns (agent_id, match_score) best
    first; match_score is 1 minus cosine distance, already in 0 to 1. This is the
    hiring primitive the broker calls in B2."""
    query = (
        Query(f"*=>[KNN {k} @{VECTOR_FIELD} $vec AS score]")
        .sort_by("score")
        .return_fields("score")
        .paging(0, k)
        .dialect(2)
    )
    res = await r.ft(INDEX_NAME).search(query, query_params={"vec": query_vector_bytes})
    out = []
    for doc in res.docs:
        agent_id = to_str(doc.id).split(":", 1)[1]
        distance = float(to_str(doc.score))
        out.append((agent_id, max(0.0, 1.0 - distance)))
    return out


async def leaderboard(r, top: int = 10) -> list[tuple[str, float]]:
    rows = await r.zrevrange(LEADERBOARD_KEY, 0, top - 1, withscores=True)
    return [(to_str(member), float(score)) for member, score in rows]