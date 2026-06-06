"""
Registry: the Redis projection and the hiring index.
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
    MODEL_PREFIX,
    MODEL_PRICES_KEY,
    PRICE_HISTORY_KEY,
    SCORED_PREFIX,
    STREAM_KEY,
    TASK_PREFIX,
    VECTOR_DIM,
    VECTOR_FIELD,
    VECTOR_METRIC,
)
from backend.db import repo
from backend.db.models import Model as ModelORM
from backend.infra.retry import with_redis_retry
from backend.infra.util import to_str


def agent_key(agent_id: str) -> str:
    return f"{AGENT_PREFIX}{agent_id}"


def model_key(model_id: str) -> str:
    return f"{MODEL_PREFIX}{model_id}"


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
        "margin": str(agent.margin),
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
        margin=float(d["margin"]),
        hires=int(d["hires"]),
        wins=int(d["wins"]),
        service_url=(d.get("service_url") or None),
    )


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
        pass


async def reset_redis(r) -> None:
    await drop_index(r)
    async for key in r.scan_iter(match=f"{AGENT_PREFIX}*"):
        await r.delete(key)
    async for key in r.scan_iter(match=f"{MODEL_PREFIX}*"):
        await r.delete(key)
    async for key in r.scan_iter(match=f"{TASK_PREFIX}*"):
        await r.delete(key)
    await r.delete(LEADERBOARD_KEY)
    await r.delete(MODEL_PRICES_KEY)
    await r.delete(PRICE_HISTORY_KEY)
    await r.delete(STREAM_KEY)


async def project_agent(r, agent: Agent, vector_bytes: bytes) -> None:
    await r.hset(agent_key(agent.agent_id), mapping=agent_to_mapping(agent, vector_bytes))
    await r.zadd(LEADERBOARD_KEY, {agent.agent_id: agent.reputation})


async def project_model(r, m: ModelORM) -> None:
    price = float(m.pool_credits) / float(m.pool_shares)
    await r.hset(
        model_key(m.model_id),
        mapping={
            "model_id": m.model_id,
            "name": m.name,
            "provider": m.provider,
            "tier": m.tier,
            "executable": "1" if m.executable else "0",
            "shares": str(float(m.pool_shares)),
            "credits": str(float(m.pool_credits)),
            "price": str(price),
            "ipo_price": str(float(m.ipo_price)),
        },
    )
    await r.zadd(MODEL_PRICES_KEY, {m.model_id: price})


async def update_leaderboard(r, agent_id: str, reputation: float) -> None:
    await r.zadd(LEADERBOARD_KEY, {agent_id: reputation})


async def reproject_agent(r, session, agent_id: str) -> None:
    """Rebuild agent hash from Postgres, preserving the existing capability vector."""
    a = await repo.get_agent(session, agent_id)
    if a is None:
        return
    vector_bytes = await r.hget(agent_key(agent_id), VECTOR_FIELD)
    if vector_bytes is None:
        return
    await project_agent(r, a, vector_bytes)


async def get_agent_cached(r, agent_id: str) -> Agent | None:
    async def _read():
        return await r.hgetall(agent_key(agent_id))

    mapping = await with_redis_retry(_read)
    if not mapping:
        return None
    return mapping_to_agent(mapping)


async def get_model_cached(r, model_id: str) -> dict | None:
    async def _read():
        return await r.hgetall(model_key(model_id))

    mapping = await with_redis_retry(_read)
    if not mapping:
        return None
    return {to_str(k): to_str(v) for k, v in mapping.items()}


async def get_model_price(r, model_id: str) -> float | None:
    p = await r.hget(model_key(model_id), "price")
    return float(to_str(p)) if p is not None else None


async def read_price_history(r, count: int = 500) -> list[dict]:
    """Recent price ticks from the Redis stream, oldest first."""
    entries = await r.xrevrange(PRICE_HISTORY_KEY, count=count)
    entries.reverse()
    out: list[dict] = []
    for entry_id, fields in entries:
        row = {to_str(k): to_str(v) for k, v in fields.items()}
        row["id"] = to_str(entry_id)
        if "price" in row:
            row["price"] = float(row["price"])
        out.append(row)
    return out


async def search(r, query_vector_bytes: bytes, k: int = 5) -> list[tuple[str, float]]:
    query = (
        Query(f"*=>[KNN {k} @{VECTOR_FIELD} $vec AS score]")
        .sort_by("score")
        .return_fields("score")
        .paging(0, k)
        .dialect(2)
    )

    async def _search():
        return await r.ft(INDEX_NAME).search(query, query_params={"vec": query_vector_bytes})

    res = await with_redis_retry(_search)
    out = []
    for doc in res.docs:
        agent_id = to_str(doc.id).split(":", 1)[1]
        distance = float(to_str(doc.score))
        out.append((agent_id, max(0.0, 1.0 - distance)))
    return out


async def leaderboard(r, top: int = 10) -> list[tuple[str, float]]:
    rows = await r.zrevrange(LEADERBOARD_KEY, 0, top - 1, withscores=True)
    return [(to_str(member), float(score)) for member, score in rows]


async def subtask_already_scored(r, subtask_id: str) -> bool:
    """True when this subtask was already scored (idempotent guard)."""
    key = f"{SCORED_PREFIX}{subtask_id}"

    async def _claim():
        return await r.setnx(key, b"1")

    claimed = await with_redis_retry(_claim)
    return not claimed
