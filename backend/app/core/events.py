"""In-process pub/sub for live telemetry, used by the SSE stream.

A single FastAPI process owns both ingestion and the dashboard streams, so an
in-memory broker is the right tool — no Redis or message queue (see the project
non-goals). Each open stream gets a bounded ``asyncio.Queue``; ingestion fans a
reading out to every subscriber of that device. A slow consumer drops events
rather than ever blocking ingestion.
"""

import asyncio
from collections import defaultdict


class TelemetryBroker:
    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, device_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[device_id].add(queue)
        return queue

    def unsubscribe(self, device_id: int, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(device_id)
        if subs is None:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(device_id, None)

    def publish(self, device_id: int, event: dict) -> None:
        for queue in list(self._subscribers.get(device_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop for a slow consumer; never block ingestion

    def subscriber_count(self, device_id: int) -> int:
        return len(self._subscribers.get(device_id, ()))


_broker = TelemetryBroker()


def get_broker() -> TelemetryBroker:
    return _broker
