from __future__ import annotations

import asyncio
from collections import defaultdict

from specpilot_backend.models.events import TraceEvent


class InMemoryRunEventBus:
    def __init__(self) -> None:
        self._events: dict[str, list[TraceEvent]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue[TraceEvent]]] = defaultdict(list)

    async def publish(self, event: TraceEvent) -> None:
        self._events[event.run_id].append(event)
        for queue in list(self._subscribers[event.run_id]):
            await queue.put(event)

    async def replay(self, run_id: str) -> list[TraceEvent]:
        return list(self._events[run_id])

    async def subscribe(self, run_id: str):
        queue: asyncio.Queue[TraceEvent] = asyncio.Queue()
        for event in self._events[run_id]:
            await queue.put(event)
        self._subscribers[run_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[run_id].remove(queue)


_GLOBAL_EVENT_BUS = InMemoryRunEventBus()


def get_event_bus() -> InMemoryRunEventBus:
    return _GLOBAL_EVENT_BUS
