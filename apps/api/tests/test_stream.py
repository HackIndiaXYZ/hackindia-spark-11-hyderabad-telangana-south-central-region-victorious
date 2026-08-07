"""The live engineering activity stream.

SSE is awkward to test through a client that buffers, so these exercise the
frame formatting directly and the endpoint through a real streaming request.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import (
    DatabaseSettings,
    Environment,
    LLMProvider,
    LLMSettings,
    ObservabilitySettings,
    Settings,
)
from app.db.session import Database
from app.domain.events import EventType, ProjectEvent
from app.events.bus import EventBus
from app.events.sse import format_event, format_heartbeat, format_open, format_retry
from app.main import create_app
from app.memory.repository import SharedMemory

PREFIX = "/api/v1"


# --- Frame format -------------------------------------------------------------


def make_event(summary: str = "Product Manager started") -> ProjectEvent:
    return ProjectEvent(
        project_id="prj_test",
        type=EventType.AGENT_STARTED,
        summary=summary,
        payload={"run_id": "run_1"},
    )


def test_event_frame_carries_id_type_and_data() -> None:
    """The id is what a reconnecting browser echoes back as Last-Event-ID."""
    event = make_event()

    frame = format_event(event)

    assert frame.startswith(f"id: {event.id}\n")
    assert "event: agent_started\n" in frame
    assert frame.endswith("\n\n")

    data = json.loads(frame.split("data: ", 1)[1].strip())
    assert data["summary"] == "Product Manager started"
    assert data["payload"]["run_id"] == "run_1"


def test_event_frame_is_a_single_line_of_data() -> None:
    """A newline inside `data:` would split the frame into two malformed ones."""
    frame = format_event(make_event("Line one\nline two"))

    data_lines = [line for line in frame.split("\n") if line.startswith("data: ")]
    assert len(data_lines) == 1


def test_heartbeat_is_a_comment_frame() -> None:
    """Comments keep the socket alive without reaching the application."""
    assert format_heartbeat().startswith(":")
    assert format_heartbeat().endswith("\n\n")


def test_retry_and_open_frames_are_well_formed() -> None:
    assert format_retry().startswith("retry: ")
    assert "event: stream_open" in format_open()


# --- Endpoint -----------------------------------------------------------------


@pytest_asyncio.fixture
async def api() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(
            url="sqlite+aiosqlite:///file:streamdb?mode=memory&cache=shared&uri=true"
        ),
        llm=LLMSettings(provider=LLMProvider.FIXTURE),
        observability=ObservabilitySettings(log_level="ERROR", json_logs=False),
    )
    app = create_app(settings)

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        await app.state.container.resolve(Database).create_schema()
        client.app_ref = app  # type: ignore[attr-defined]
        yield client


async def create_project(api: AsyncClient) -> str:
    response = await api.post(
        f"{PREFIX}/projects",
        json={"name": "Hospital System", "description": "Patients and appointments."},
    )
    return response.json()["id"]


class FakeRequest:
    """A request that reports disconnection after a set number of checks.

    The stream is deliberately infinite, so an HTTP client would need the server
    to close it — and an in-process ASGI transport never signals disconnect.
    Driving the generator directly tests the real logic (replay, handover,
    heartbeat, dedupe) while remaining bounded.
    """

    def __init__(self, checks_before_disconnect: int = 1) -> None:
        self._remaining = checks_before_disconnect

    async def is_disconnected(self) -> bool:
        if self._remaining <= 0:
            return True
        self._remaining -= 1
        return False


async def collect(api: AsyncClient, project_id: str, **kwargs: object) -> str:
    """Drive the stream generator to completion and return its frames."""
    from app.api.routers.stream import _stream

    container = api.app_ref.state.container  # type: ignore[attr-defined]
    bus = container.resolve(EventBus)
    memory = container.resolve(SharedMemory)  # type: ignore[type-abstract]

    frames = [
        frame
        async for frame in _stream(
            FakeRequest(kwargs.get("checks", 1)),  # type: ignore[arg-type]
            bus,
            memory,
            project_id,
            kwargs.get("last_event_id"),  # type: ignore[arg-type]
            heartbeat_seconds=0.05,
        )
    ]
    return "".join(frames)


async def test_stream_opens_with_retry_and_replays_history(api: AsyncClient) -> None:
    """A client joining mid-project sees what already happened."""
    project_id = await create_project(api)

    output = await collect(api, project_id)

    assert output.startswith("retry: ")
    assert "event: stream_open" in output
    assert "event: project_created" in output


async def test_last_event_id_skips_what_the_client_already_saw(
    api: AsyncClient,
) -> None:
    project_id = await create_project(api)
    seen = (await api.get(f"{PREFIX}/projects/{project_id}/events")).json()

    output = await collect(api, project_id, last_event_id=seen[-1]["id"])

    assert "event: stream_open" in output
    assert "event: project_created" not in output


async def test_replayed_events_are_not_sent_twice(api: AsyncClient) -> None:
    """Subscribing before replaying can duplicate; the dedupe set prevents it."""
    project_id = await create_project(api)

    container = api.app_ref.state.container  # type: ignore[attr-defined]
    bus = container.resolve(EventBus)
    memory = container.resolve(SharedMemory)  # type: ignore[type-abstract]

    # Publish through the bus so the event is both persisted and queued, which is
    # exactly the handover race the dedupe guards.
    from app.api.routers.stream import _stream

    async with bus.subscribe(project_id):
        published = await bus.publish(
            ProjectEvent(
                project_id=project_id,
                type=EventType.AGENT_STARTED,
                summary="Product Manager started",
            )
        )

    frames = [
        frame
        async for frame in _stream(
            FakeRequest(2),  # type: ignore[arg-type]
            bus,
            memory,
            project_id,
            None,
            heartbeat_seconds=0.05,
        )
    ]
    output = "".join(frames)

    assert output.count(f"id: {published.id}") == 1
    assert "event: agent_started" in output


async def test_stream_disconnects_cleanly(api: AsyncClient) -> None:
    """A closed browser tab must not leave a subscriber attached to the bus."""
    project_id = await create_project(api)
    bus: EventBus = api.app_ref.state.container.resolve(EventBus)  # type: ignore[attr-defined]

    await collect(api, project_id)

    assert bus.subscriber_count(project_id) == 0


async def test_stream_for_unknown_project_is_a_404(api: AsyncClient) -> None:
    """Checked before the stream opens, so it is a real status not an error frame."""
    async with api.stream(
        "GET", f"{PREFIX}/projects/prj_missing/events/stream"
    ) as response:
        assert response.status_code == 404


# --- Bus behaviour under streaming --------------------------------------------


async def test_publishing_reaches_a_live_subscriber(api: AsyncClient) -> None:
    """The property the whole view depends on: publisher and stream share a bus."""
    project_id = await create_project(api)
    bus: EventBus = api.app_ref.state.container.resolve(EventBus)  # type: ignore[attr-defined]

    async with bus.subscribe(project_id) as queue:
        await bus.publish(
            ProjectEvent(
                project_id=project_id,
                type=EventType.AGENT_COMPLETED,
                summary="Architect finished",
            )
        )

        received = await asyncio.wait_for(queue.get(), timeout=2)

    assert received.summary == "Architect finished"


async def test_advancing_publishes_to_a_live_subscriber(api: AsyncClient) -> None:
    """Running the organization emits activity a stream would carry."""
    project_id = await create_project(api)
    bus: EventBus = api.app_ref.state.container.resolve(EventBus)  # type: ignore[attr-defined]

    async with bus.subscribe(project_id) as queue:
        await api.post(f"{PREFIX}/projects/{project_id}/advance")

        received = []
        while not queue.empty():
            received.append(queue.get_nowait())

    types = {event.type for event in received}
    assert EventType.AGENT_STARTED in types
    assert EventType.ARTIFACT_CREATED in types
    assert EventType.AGENT_COMPLETED in types


@pytest.mark.parametrize("subscribers", [1, 3])
async def test_every_open_stream_receives_the_event(
    api: AsyncClient, subscribers: int
) -> None:
    """Several browser tabs on one project all see the same activity."""
    project_id = await create_project(api)
    bus: EventBus = api.app_ref.state.container.resolve(EventBus)  # type: ignore[attr-defined]

    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        queues = [
            await stack.enter_async_context(bus.subscribe(project_id))
            for _ in range(subscribers)
        ]

        await bus.publish(
            ProjectEvent(
                project_id=project_id,
                type=EventType.STAGE_COMPLETED,
                summary="Architecture completed",
            )
        )

        for queue in queues:
            event = await asyncio.wait_for(queue.get(), timeout=2)
            assert event.summary == "Architecture completed"
