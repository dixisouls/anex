"""
Event feed (async).

The single emit() helper every module goes through to write a market event.
Nobody hand-rolls an XADD. Track B's broker, ledger, and upgrade call this, and
Track A's judge imports it to emit task_scored. The models in contracts/events.py
auto-fill event_id and ts, so the stream stays consistent.

The /feed endpoint (B4) will read entries and forward them as server sent events.
read_new() here is the same read, used by tests and the SSE loop.
"""

from contracts.events import EVENT_ADAPTER, MarketEvent
from backend.config import STREAM_KEY
from backend.infra.retry import with_redis_retry
from backend.infra.util import to_str


async def emit(r, event: MarketEvent) -> str:
    """Append an event to market:feed. Returns the stream entry id."""
    payload = event.model_dump_json()

    async def _xadd() -> bytes | str:
        return await r.xadd(STREAM_KEY, {"data": payload})

    entry_id = await with_redis_retry(_xadd)
    return to_str(entry_id)


async def read_new(r, last_id: str = "0-0", count: int = 100, block: int | None = None):
    """Read entries after last_id. Returns (entry_id, event) pairs, event a
    validated model. Page forward by passing back the last entry_id, or block
    (ms) to wait for new entries. The SSE endpoint in B4 uses this loop."""
    res = await r.xread({STREAM_KEY: last_id}, count=count, block=block)
    out = []
    if res:
        _stream, entries = res[0]
        for entry_id, fields in entries:
            raw = fields.get(b"data") or fields.get("data")
            out.append((to_str(entry_id), EVENT_ADAPTER.validate_json(to_str(raw))))
    return out


async def read_recent(r, count: int = 200):
    """Read the newest count entries, returned oldest-first for SSE replay."""
    entries = await r.xrevrange(STREAM_KEY, count=count)
    out = []
    for entry_id, fields in reversed(entries):
        raw = fields.get(b"data") or fields.get("data")
        out.append((to_str(entry_id), EVENT_ADAPTER.validate_json(to_str(raw))))
    return out