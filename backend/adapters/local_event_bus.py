"""Local EventBus: Redis Stream (market:feed) via feed.emit / feed.read_new."""

from collections.abc import AsyncIterator

from contracts.events import EVENT_ADAPTER, MarketEvent
from backend.config import STREAM_KEY
from backend.infra.redis_client import get_redis
from backend.infra.util import to_str
from backend.market import feed


class LocalEventBus:
    async def publish(self, event: MarketEvent) -> None:
        await feed.emit(get_redis(), event)

    def subscribe(self, *, from_id: str = "$") -> AsyncIterator[tuple[str, MarketEvent]]:
        return self._subscribe(from_id)

    async def _subscribe(self, from_id: str) -> AsyncIterator[tuple[str, MarketEvent]]:
        r = get_redis()
        cursor = from_id
        while True:
            if cursor == "$":
                res = await r.xread({STREAM_KEY: "$"}, block=5000)
                if not res:
                    continue
                _stream, raw_entries = res[0]
                for entry_id, fields in raw_entries:
                    cursor = to_str(entry_id)
                    raw = fields.get(b"data") or fields.get("data")
                    yield cursor, EVENT_ADAPTER.validate_json(to_str(raw))
            else:
                entries = await feed.read_new(r, last_id=cursor, block=5000)
                if not entries:
                    continue
                for entry_id, event in entries:
                    cursor = entry_id
                    yield entry_id, event
