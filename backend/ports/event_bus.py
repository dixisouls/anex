"""EventBus port: publish market events and subscribe for SSE replay."""

from typing import AsyncIterator, Protocol

from contracts.events import MarketEvent


class EventBus(Protocol):
    async def publish(self, event: MarketEvent) -> None: ...

    def subscribe(
        self, *, from_id: str = "$"
    ) -> AsyncIterator[tuple[str, MarketEvent]]: ...
