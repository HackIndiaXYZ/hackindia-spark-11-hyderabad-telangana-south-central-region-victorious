"""Event bus: durable append plus live fan-out."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest_asyncio

from app.core.config import DatabaseSettings
from app.db.session import Database
from app.domain.events import EventType, ProjectEvent
from app.domain.projects import Project
from app.events.bus import EventBus
from app.memory.sql_repository import SqlSharedMemory


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:busdb?mode=memory&cache=shared&uri=true")
    )
    await database.create_schema()
    try:
        yield SqlSharedMemory(database)
    finally:
        await database.aclose()


@pytest_asyncio.fixture
async def project(memory: SqlSharedMemory) -> Project:
    return await memory.projects.create(Project(name="Demo", description="A demo project."))


def event(project_id: str, summary: str = "Agent completed") -> ProjectEvent:
    return ProjectEvent(
        project_id=project_id, type=EventType.AGENT_COMPLETED, summary=summary
    )


async def test_published_events_are_persisted(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Durability first: the timeline must agree with what the user watched."""
    bus = EventBus(memory.events)

    await bus.publish(event(project.id, "Product Manager finished"))

    stored = await memory.events.list_for_project(project.id)
    assert [e.summary for e in stored] == ["Product Manager finished"]


async def test_subscriber_receives_live_events(
    memory: SqlSharedMemory, project: Project
) -> None:
    bus = EventBus(memory.events)

    async with bus.subscribe(project.id) as queue:
        await bus.publish(event(project.id, "Architect started"))

        received = await asyncio.wait_for(queue.get(), timeout=2)

    assert received.summary == "Architect started"


async def test_subscribers_are_scoped_to_their_project(
    memory: SqlSharedMemory, project: Project
) -> None:
    other = await memory.projects.create(Project(name="Other", description="Unrelated."))
    bus = EventBus(memory.events)

    async with bus.subscribe(project.id) as queue:
        await bus.publish(event(other.id, "Unrelated activity"))

        assert queue.empty()


async def test_multiple_subscribers_each_receive_the_event(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Two browser tabs on the same project both see agent activity."""
    bus = EventBus(memory.events)

    async with bus.subscribe(project.id) as first, bus.subscribe(project.id) as second:
        await bus.publish(event(project.id, "Stage completed"))

        assert (await asyncio.wait_for(first.get(), timeout=2)).summary == "Stage completed"
        assert (await asyncio.wait_for(second.get(), timeout=2)).summary == "Stage completed"


async def test_subscriber_is_unregistered_on_exit(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A closed browser tab must not leak a queue the publisher keeps filling."""
    bus = EventBus(memory.events)

    async with bus.subscribe(project.id):
        assert bus.subscriber_count(project.id) == 1

    assert bus.subscriber_count(project.id) == 0


async def test_subscriber_is_unregistered_when_the_block_raises(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A client disconnecting mid-stream raises; cleanup must still happen."""
    bus = EventBus(memory.events)

    try:
        async with bus.subscribe(project.id):
            raise ConnectionResetError("client went away")
    except ConnectionResetError:
        pass

    assert bus.subscriber_count(project.id) == 0


async def test_publication_succeeds_with_no_subscribers(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Agent work is not contingent on anyone watching."""
    bus = EventBus(memory.events)

    published = await bus.publish(event(project.id))

    assert published.id.startswith("evt_")
    assert len(await memory.events.list_for_project(project.id)) == 1


async def test_slow_subscriber_does_not_block_publication(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A stalled consumer drops its oldest events rather than stalling the platform."""
    bus = EventBus(memory.events)
    total = 400

    async with bus.subscribe(project.id) as queue:
        for index in range(total):
            await bus.publish(event(project.id, f"event {index}"))

        # Every event reached durable storage regardless of the queue overflowing.
        assert len(await memory.events.list_for_project(project.id, limit=1000)) == total
        assert queue.qsize() <= 256
