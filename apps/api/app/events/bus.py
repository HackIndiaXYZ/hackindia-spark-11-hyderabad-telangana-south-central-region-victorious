"""In-process event bus.

Publishing an event does two things: it appends to the durable record in shared
memory, and it fans out to live subscribers. Milestone 6 subscribes the SSE
endpoint here, so the browser sees agent activity as it happens while the
timeline can still be reconstructed after a reload.

Subscribers must never be able to break publication. An agent's work is not
invalidated because a browser connection dropped mid-write, so a failing
subscriber is logged and skipped.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.logging import get_logger
from app.domain.events import ProjectEvent
from app.memory.repository import EventRepository

logger = get_logger(__name__)

#: Bounded so a stalled consumer cannot grow memory without limit. On overflow
#: the oldest event is dropped for that subscriber only; it reconnects with
#: ``after_id`` and replays what it missed from the durable record.
_SUBSCRIBER_QUEUE_SIZE = 256


class EventBus:
    """Durable append plus live fan-out."""

    def __init__(self, events: EventRepository) -> None:
        self._events = events
        self._subscribers: dict[str, set[asyncio.Queue[ProjectEvent]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: ProjectEvent) -> ProjectEvent:
        """Persist an event, then deliver it to live subscribers.

        Persistence happens first and deliberately: an event that reached a
        browser but was never recorded would leave the timeline disagreeing with
        what the user watched happen.
        """
        stored = await self._events.append(event)

        async with self._lock:
            queues = list(self._subscribers.get(event.project_id, ()))

        for queue in queues:
            try:
                queue.put_nowait(stored)
            except asyncio.QueueFull:
                # Drop the oldest for this subscriber and retry once; it will
                # reconcile on reconnect.
                try:
                    queue.get_nowait()
                    queue.put_nowait(stored)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    logger.warning(
                        "Dropped event for slow subscriber",
                        extra={"project_id": event.project_id, "event_type": event.type.value},
                    )

        return stored

    @asynccontextmanager
    async def subscribe(self, project_id: str) -> AsyncIterator[asyncio.Queue[ProjectEvent]]:
        """Subscribe to a project's live events for the duration of the block.

        The queue is always unregistered on exit, including when the client
        disconnects mid-stream, so a dropped browser tab cannot leak a queue that
        the publisher keeps filling forever.
        """
        queue: asyncio.Queue[ProjectEvent] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)

        async with self._lock:
            self._subscribers.setdefault(project_id, set()).add(queue)

        logger.debug("Event subscriber attached", extra={"project_id": project_id})

        try:
            yield queue
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(project_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        del self._subscribers[project_id]

            logger.debug("Event subscriber detached", extra={"project_id": project_id})

    def subscriber_count(self, project_id: str) -> int:
        """Return the number of live subscribers. Used by tests and diagnostics."""
        return len(self._subscribers.get(project_id, ()))
