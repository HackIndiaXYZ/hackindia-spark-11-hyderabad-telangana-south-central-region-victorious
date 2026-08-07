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


# Named aliases keep router signatures readable as the dependency set grows.
ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
HealthRegistryDep = Annotated[HealthRegistry, Depends(get_health_registry)]
