"""Application composition root.

Every concrete implementation is chosen here and nowhere else. Modules depend on
protocols; this file is the single place that says which implementation backs
each one. Moving a swap decision into this file is what keeps the rest of the
codebase free of conditional wiring.

Each milestone extends ``build_container`` with its own registrations:
Milestone 2 the LLM provider registry, Milestone 3 the orchestrator.
"""

from __future__ import annotations

import time

from app.core.config import Settings
from app.core.container import Container
from app.core.health import ComponentHealth, HealthRegistry, HealthStatus
from app.core.logging import get_logger
from app.db.session import Database
from app.events.bus import EventBus
from app.memory.context_builder import ContextBuilder
from app.memory.health import DatabaseHealthCheck
from app.memory.repository import SharedMemory
from app.memory.sql_repository import SqlSharedMemory

logger = get_logger(__name__)


class ProcessHealthCheck:
    """Reports that the API process itself is serving requests.

    Trivially healthy by construction — if it can answer, the process is alive —
    but it carries uptime, which distinguishes a stable service from one caught
    in a crash-restart loop.
    """

    def __init__(self) -> None:
        self._started_at = time.monotonic()

    @property
    def name(self) -> str:
        return "api"

    @property
    def critical(self) -> bool:
        return True

    async def check(self) -> ComponentHealth:
        uptime = time.monotonic() - self._started_at
        return ComponentHealth(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message=f"Serving for {uptime:.1f}s",
        )


def build_container(settings: Settings) -> Container:
    """Construct and wire the application container.

    Args:
        settings: Resolved configuration. Passed explicitly rather than read from
            the environment so tests can build a container against any config.

    Returns:
        A container with every protocol required at the current milestone bound
        to an implementation.
    """
    container = Container()

    container.register_instance(Settings, settings)

    # --- Persistence and shared organizational memory ------------------------
    # The Database singleton owns the engine; the container disposes it on
    # shutdown through its `aclose` hook.
    database = Database(settings.database)
    container.register_instance(Database, database)

    memory = SqlSharedMemory(database)
    # Registered against the protocol, not the concrete class: this is the swap
    # point ADR-0003 exists to preserve. Nothing downstream names SqlSharedMemory.
    container.register_instance(SharedMemory, memory)  # type: ignore[type-abstract]

    container.register_singleton(
        ContextBuilder,
        lambda: ContextBuilder(memory.projects, memory.artifacts),
    )

    container.register_instance(EventBus, EventBus(memory.events))

    # --- Health --------------------------------------------------------------
    health_registry = HealthRegistry()
    health_registry.register(ProcessHealthCheck())
    health_registry.register(DatabaseHealthCheck(database))
    container.register_instance(HealthRegistry, health_registry)

    logger.info(
        "Container built",
        extra={
            "environment": settings.environment.value,
            "llm_provider": settings.llm.provider.value,
            "vector_store_enabled": settings.vector_store.enabled,
        },
    )
    return container
