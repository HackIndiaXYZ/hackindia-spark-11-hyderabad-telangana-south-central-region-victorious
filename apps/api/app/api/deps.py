"""FastAPI dependency providers.

Bridges the application-scoped container onto FastAPI's request-scoped injection
so routers declare what they need as typed parameters and never reach for a
global.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.container import Container
from app.core.health import HealthRegistry
from app.memory.repository import SharedMemory
from app.orchestration.runner import OrchestrationRunner


def get_container(request: Request) -> Container:
    """Return the container attached to the application at startup."""
    container: Container = request.app.state.container
    return container


def get_settings_dep(container: Annotated[Container, Depends(get_container)]) -> Settings:
    """Resolve application settings."""
    return container.resolve(Settings)


def get_health_registry(
    container: Annotated[Container, Depends(get_container)],
) -> HealthRegistry:
    """Resolve the health check registry."""
    return container.resolve(HealthRegistry)


def get_memory(container: Annotated[Container, Depends(get_container)]) -> SharedMemory:
    """Resolve the shared organizational memory.

    Resolved by protocol, not by concrete class, so the SQL implementation could
    be swapped without touching a single router (ADR-0003).
    """
    return container.resolve(SharedMemory)  # type: ignore[type-abstract]


def get_runner(
    container: Annotated[Container, Depends(get_container)],
) -> OrchestrationRunner:
    """Resolve the orchestration runner."""
    return container.resolve(OrchestrationRunner)


# Named aliases keep router signatures readable as the dependency set grows.
ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
HealthRegistryDep = Annotated[HealthRegistry, Depends(get_health_registry)]
MemoryDep = Annotated[SharedMemory, Depends(get_memory)]
RunnerDep = Annotated[OrchestrationRunner, Depends(get_runner)]
