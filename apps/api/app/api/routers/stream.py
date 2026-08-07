"""Live engineering activity stream.

`07_System_Architecture.md` requires users to "observe the complete AI
Engineering Organization operating in real time", and `10_UI_UX_Plan.md`
forbids hiding agent execution behind loading indicators. This endpoint is how
the workspace sees work as it happens rather than after it finishes.

The stream carries *signals*, not state. A client reacts to an event by re-reading
the REST endpoint it cares about, so there is exactly one projection of agent and
artifact state — the API's — rather than a second one assembled in the browser
that can drift from it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.api.deps import EventBusDep, MemoryDep
from app.core.logging import get_logger
from app.events.bus import EventBus
from app.events.sse import (
    HEARTBEAT_SECONDS,
    format_event,
    format_heartbeat,
    format_open,
    format_retry,
)
from app.memory.repository import SharedMemory

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["stream"])

#: Events replayed at most on reconnection. A browser that has been closed for an
#: hour wants recent history, not the entire project.
REPLAY_LIMIT = 200


async def _stream(
    request: Request,
    bus: EventBus,
    memory: SharedMemory,
    project_id: str,
    last_event_id: str | None,
    *,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Yield SSE frames until the client disconnects.

    Subscription happens *before* the replay read, deliberately. Reading first
    and subscribing afterwards would drop anything published in between — a
    window that lands precisely when the organization is busiest, which is when
    the stream matters most. Subscribing first can instead duplicate an event
    that appears in both, so replayed identifiers are remembered and skipped.

    ``heartbeat_seconds`` is injectable so tests exercise the idle path without
    waiting the production interval for every case.
    """
    async with bus.subscribe(project_id) as queue:
        yield format_retry()
        yield format_open()

        replayed: set[str] = set()
        for event in await memory.events.list_for_project(
            project_id, limit=REPLAY_LIMIT, after_id=last_event_id
        ):
            replayed.add(event.id)
            yield format_event(event)

        while True:
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield format_heartbeat()
                continue

            if event.id in replayed:
                continue

            # The replay set only guards the handover; once a live event arrives
            # the window has closed and holding the set would leak.
            replayed.clear()
            yield format_event(event)

    logger.debug("Event stream closed", extra={"project_id": project_id})


@router.get(
    "/{project_id}/events/stream",
    summary="Live engineering activity (SSE)",
    response_class=StreamingResponse,
)
async def stream_events(
    project_id: str,
    request: Request,
    bus: EventBusDep,
    memory: MemoryDep,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Stream the project's engineering activity as it happens.

    Reconnecting browsers send ``Last-Event-ID`` automatically; everything missed
    while disconnected is replayed before the live feed resumes.
    """
    # Existence is checked before the stream opens: a 404 inside a streaming
    # response would arrive as a 200 with an error frame, which no EventSource
    # client would treat as a failure.
    await memory.projects.get(project_id)

    return StreamingResponse(
        _stream(request, bus, memory, project_id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Nginx buffers proxied responses by default, which would hold every
            # frame until the stream ended — defeating the point entirely.
            "X-Accel-Buffering": "no",
        },
    )
