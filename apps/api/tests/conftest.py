"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import (
    DatabaseSettings,
    Environment,
    LLMProvider,
    LLMSettings,
    ObservabilitySettings,
    Settings,
)
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Isolated test configuration.

    Constructed explicitly rather than read from the environment so the suite is
    deterministic regardless of the developer's shell. Uses an in-memory database
    and the fixture LLM provider: tests must never make a network call.
    """
    return Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(url="sqlite+aiosqlite:///:memory:"),
        llm=LLMSettings(provider=LLMProvider.FIXTURE),
        observability=ObservabilitySettings(log_level="WARNING", json_logs=False),
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the app in-process.

    ``ASGITransport`` exercises the real middleware and handler stack without
    binding a socket.
    """
    app = create_app(settings)

    # The lifespan context is entered alongside the client so the container is
    # built exactly as it is in production, rather than stubbed for tests.
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client,
        app.router.lifespan_context(app),
    ):
        yield async_client
