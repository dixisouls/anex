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
from datetime import datetime, timezone

from backend.config import (
    AGENT_PREFIX,
    HISTORY_PER_MODEL,
    INDEX_NAME,
    LEADERBOARD_KEY,
    MARKET_SESSION_KEY,
    MODEL_PREFIX,
    MODEL_PRICES_KEY,
    PRICE_HISTORY_KEY,
    PRICE_HISTORY_PREFIX,
    SCORED_PREFIX,
    STREAM_KEY,
    TASK_PREFIX,
    VECTOR_DIM,
    VECTOR_FIELD,
    VECTOR_METRIC,
)
from backend.market import dynamics
from backend.db import repo
from backend.db.models import Model as ModelORM
from backend.infra.retry import with_redis_retry
from backend.infra.util import to_str


def agent_key(agent_id: str) -> str:
    return f"{AGENT_PREFIX}{agent_id}"


def model_key(model_id: str) -> str:
    return f"{MODEL_PREFIX}{model_id}"


def _infer_capability_id(agent_id: str) -> str:
    for suffix in ("-pro", "-flash", "-lite"):
        if agent_id.endswith(suffix):
            return agent_id[: -len(suffix)]
    return agent_id


def agent_embed_text(agent: Agent) -> str:
    """Document text projected into the hiring index. Includes name and skills
    so retrieval aligns with how subtasks are phrased, not just the prose blurb."""
    skills = ", ".join(agent.skills)
    return f"{agent.name}. Skills: {skills}. {agent.capability_text}"


def agent_to_mapping(agent: Agent, vector_bytes: bytes | None = None) -> dict:
    mapping = {
        "agent_id": agent.agent_id,
        "capability_id": agent.capability_id,
        "service_tier": agent.service_tier,
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
    }
    if vector_bytes is not None:
        mapping[VECTOR_FIELD] = vector_bytes
    return mapping


def mapping_to_agent(mapping: dict) -> Agent:
    d = {}
    for raw_key, raw_val in mapping.items():
        key = to_str(raw_key)
        if key == VECTOR_FIELD:
            continue
        d[key] = to_str(raw_val)
    return Agent(
        agent_id=d["agent_id"],
        capability_id=d.get("capability_id") or _infer_capability_id(d["agent_id"]),
        service_tier=d.get("service_tier", "flash"),  # type: ignore[arg-type]
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


def price_history_key(model_id: str) -> str:
    return f"{PRICE_HISTORY_PREFIX}{model_id}"


async def reset_redis(r) -> None:
    await drop_index(r)
    async for key in r.scan_iter(match=f"{AGENT_PREFIX}*"):
        await r.delete(key)
    async for key in r.scan_iter(match=f"{MODEL_PREFIX}*"):
        await r.delete(key)
    async for key in r.scan_iter(match=f"{TASK_PREFIX}*"):
        await r.delete(key)
    async for key in r.scan_iter(match=f"{PRICE_HISTORY_PREFIX}*"):
        await r.delete(key)
    await r.delete(LEADERBOARD_KEY)
    await r.delete(MODEL_PRICES_KEY)
    await r.delete(PRICE_HISTORY_KEY)
    await r.delete(MARKET_SESSION_KEY)
    await r.delete(STREAM_KEY)


async def project_agent(r, agent: Agent, vector_bytes: bytes | None) -> None:
    await r.hset(agent_key(agent.agent_id), mapping=agent_to_mapping(agent, vector_bytes))
    await r.zadd(LEADERBOARD_KEY, {agent.agent_id: agent.reputation})


def is_search_index_primary(agent: Agent, primary_tiers: dict[str, str]) -> bool:
    """True when this agent should be embedded in the vector hiring index."""
    expected = primary_tiers.get(agent.capability_id)
    if expected is None:
        return agent.service_tier == "pro"
    return agent.service_tier == expected


async def init_market_fields(r, model_id: str, ipo_price: float) -> None:
    """Set fundamental and session stats when a model is first listed."""
    key = model_key(model_id)
    existing = await r.hget(key, "fundamental")
    if existing is None:
        await r.hset(
            key,
            mapping={
                "fundamental": str(ipo_price),
                "session_open": str(ipo_price),
                "day_high": str(ipo_price),
                "day_low": str(ipo_price),
                "volume_24h": "0",
            },
        )
        await r.hset(MARKET_SESSION_KEY, model_id, str(ipo_price))


async def set_fundamental(r, model_id: str, value: float) -> None:
    await r.hset(model_key(model_id), "fundamental", str(value))


async def get_fundamental(r, model_id: str, fallback: float) -> float:
    raw = await r.hget(model_key(model_id), "fundamental")
    return float(to_str(raw)) if raw is not None else fallback


async def bump_session_stats(
    r, model_id: str, price: float, *, volume_delta: float = 0.0
) -> None:
    key = model_key(model_id)
    mapping = await r.hgetall(key)
    if not mapping:
        return
    d = {to_str(k): to_str(v) for k, v in mapping.items()}
    high = max(float(d.get("day_high", price)), price)
    low = min(float(d.get("day_low", price)), price)
    vol = float(d.get("volume_24h", 0)) + volume_delta
    await r.hset(
        key,
        mapping={"day_high": str(high), "day_low": str(low), "volume_24h": str(vol)},
    )


async def project_model(r, m: ModelORM) -> None:
    shares = float(m.pool_shares)
    credits = float(m.pool_credits)
    price = dynamics.pool_mid(shares, credits)
    key = model_key(m.model_id)
    prev = await r.hgetall(key)
    prev_d = {to_str(k): to_str(v) for k, v in prev.items()} if prev else {}
    fundamental = prev_d.get("fundamental", str(float(m.ipo_price)))
    session_open = prev_d.get("session_open", str(float(m.ipo_price)))
    day_high = prev_d.get("day_high", str(price))
    day_low = prev_d.get("day_low", str(price))
    volume_24h = prev_d.get("volume_24h", "0")
    bid, _ = dynamics.quote_buy(shares, credits)
    ask, _ = dynamics.quote_sell(shares, credits)
    mid = price
    spread = dynamics.spread_bps(bid, ask, mid)
    depth = dynamics.pool_depth(shares, credits)
    await r.hset(
        key,
        mapping={
            "model_id": m.model_id,
            "name": m.name,
            "provider": m.provider,
            "tier": m.tier,
            "executable": "1" if m.executable else "0",
            "shares": str(shares),
            "credits": str(credits),
            "price": str(price),
            "ipo_price": str(float(m.ipo_price)),
            "fundamental": fundamental,
            "session_open": session_open,
            "day_high": day_high,
            "day_low": day_low,
            "volume_24h": volume_24h,
            "bid": str(bid),
            "ask": str(ask),
            "spread_bps": str(spread),
            "depth": str(depth),
        },
    )
    await r.zadd(MODEL_PRICES_KEY, {m.model_id: price})


async def model_market_extras(r, model_id: str) -> dict:
    """Quote and session fields for API responses."""
    mapping = await get_model_cached(r, model_id)
    if not mapping:
        return {}
    price = float(mapping.get("price", 0))
    bid = float(mapping.get("bid", price))
    ask = float(mapping.get("ask", price))
    fundamental = float(mapping.get("fundamental", price))
    session_open = float(mapping.get("session_open", price))
    return {
        "bid": bid,
        "ask": ask,
        "spread_bps": float(mapping.get("spread_bps", 0)),
        "depth": float(mapping.get("depth", 0)),
        "fundamental": fundamental,
        "session_open": session_open,
        "day_high": float(mapping.get("day_high", price)),
        "day_low": float(mapping.get("day_low", price)),
        "volume": float(mapping.get("volume_24h", 0)),
        "vs_fair_pct": dynamics.vs_fair_pct(price, fundamental),
    }


async def append_price_tick(
    r, *, model_id: str, price: float, reason: str
) -> str:
    """Record a price tick on per-model and legacy global streams."""
    ts = datetime.now(timezone.utc).isoformat()
    fields = {"model_id": model_id, "price": str(price), "ts": ts, "reason": reason}
    entry_id = await r.xadd(price_history_key(model_id), fields)
    await r.xadd(PRICE_HISTORY_KEY, fields)
    # Trim per-model stream
    await r.xtrim(price_history_key(model_id), maxlen=HISTORY_PER_MODEL, approximate=True)
    return to_str(entry_id)


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
    """Recent price ticks from the legacy global stream, oldest first."""
    entries = await r.xrevrange(PRICE_HISTORY_KEY, count=count)
    entries.reverse()
    return _parse_history_entries(entries)


async def read_model_history(r, model_id: str, count: int = 120) -> list[dict]:
    """Per-model price ticks, oldest first."""
    entries = await r.xrevrange(price_history_key(model_id), count=count)
    entries.reverse()
    return _parse_history_entries(entries)


def _parse_history_entries(entries) -> list[dict]:
    out: list[dict] = []
    for entry_id, fields in entries:
        row = {to_str(k): to_str(v) for k, v in fields.items()}
        row["id"] = to_str(entry_id)
        if "price" in row:
            row["price"] = float(row["price"])
        out.append(row)
    return out


def aggregate_bars(ticks: list[dict], interval_s: int = 60, limit: int = 60) -> list[dict]:
    """Roll ticks into OHLCV bars by wall-clock bucket."""
    if not ticks:
        return []
    buckets: dict[int, dict] = {}
    for tick in ticks:
        ts_raw = tick.get("ts") or ""
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        bucket = int(ts.timestamp()) // interval_s
        price = float(tick["price"])
        bar = buckets.get(bucket)
        if bar is None:
            buckets[bucket] = {
                "t": bucket * interval_s,
                "o": price,
                "h": price,
                "l": price,
                "c": price,
                "v": 1,
            }
        else:
            bar["h"] = max(bar["h"], price)
            bar["l"] = min(bar["l"], price)
            bar["c"] = price
            bar["v"] += 1
    bars = sorted(buckets.values(), key=lambda b: b["t"])
    return bars[-limit:]


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
