"""Server-Sent Events framing.

ADR-0005 chose SSE over WebSockets: agent activity is strictly one-directional —
the server emits, the browser renders — and SSE does that over plain HTTP with
automatic client reconnection and no extra infrastructure.

This module owns the wire format only. Deciding *what* to stream belongs to the
router; deciding *when* belongs to the event bus.
"""

from __future__ import annotations

import json

from app.domain.events import ProjectEvent

#: How long the stream may sit silent before emitting a comment frame.
#:
#: Proxies and load balancers close idle connections, and a demo that silently
#: stops updating after a minute of an agent thinking is worse than no stream at
#: all. Comment frames are ignored by EventSource but keep the socket alive.
HEARTBEAT_SECONDS = 15.0

#: Reconnection delay advertised to the browser, in milliseconds. EventSource
#: reconnects on its own; this only tunes how eagerly.
RETRY_MS = 3000


def format_event(event: ProjectEvent) -> str:
    """Render a project event as one SSE frame.

    The ``id`` field is the event's own identifier, which the browser echoes back
    as ``Last-Event-ID`` when it reconnects. That is what makes resumption exact
    rather than approximate — the same cursor the durable event log already
    understands.
    """
    payload = {
        "id": event.id,
        "type": event.type.value,
        "stage": event.stage.value if event.stage else None,
        "role": event.role.value if event.role else None,
        "summary": event.summary,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }

    # `event:` names the frame so the client can listen selectively rather than
    # parsing every message to discover it does not care about it.
    return (
        f"id: {event.id}\n"
        f"event: {event.type.value}\n"
        f"data: {json.dumps(payload, default=str)}\n\n"
    )


def format_heartbeat() -> str:
    """A comment frame. Keeps the connection open without reaching the client."""
    return ": heartbeat\n\n"


def format_retry() -> str:
    """Advertise the reconnection delay. Sent once when the stream opens."""
    return f"retry: {RETRY_MS}\n\n"


def format_open() -> str:
    """A frame marking the stream ready, so the UI can show it is connected."""
    return 'event: stream_open\ndata: {"connected":true}\n\n'
