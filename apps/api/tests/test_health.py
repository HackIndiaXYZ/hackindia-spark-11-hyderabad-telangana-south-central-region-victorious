"""Health endpoint behaviour."""

from __future__ import annotations

from httpx import AsyncClient

from app.core.health import ComponentHealth, HealthStatus
from app.core.middleware import CORRELATION_HEADER


async def test_liveness_reports_healthy(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == HealthStatus.HEALTHY.value
    assert body["service"] == "Project Victorious"
    assert body["environment"] == "test"


async def test_readiness_reports_registered_components(client: AsyncClient) -> None:
    """Every component that registers a check appears, with no change here.

    ``shared_memory`` arrived in Milestone 1 by registering itself in the
    composition root — the readiness endpoint required no modification. Later
    milestones' components join the same way.
    """
    response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == HealthStatus.HEALTHY.value

    components = {component["name"]: component for component in body["components"]}
    assert {"api", "shared_memory"} <= set(components)
    assert components["shared_memory"]["status"] == HealthStatus.HEALTHY.value
    assert all(component["latency_ms"] >= 0 for component in components.values())


async def test_readiness_returns_503_when_critical_component_fails(
    client: AsyncClient,
) -> None:
    """A failed critical component must drain traffic, not silently return 200."""

    class FailingCheck:
        name = "database"
        critical = True

        async def check(self) -> ComponentHealth:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="connection refused",
            )

    from app.core.health import HealthRegistry

    registry = client._transport.app.state.container.resolve(HealthRegistry)  # type: ignore[union-attr]
    registry.register(FailingCheck())

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == HealthStatus.UNHEALTHY.value


async def test_readiness_stays_available_when_noncritical_component_fails(
    client: AsyncClient,
) -> None:
    """Degraded capability still serves traffic — the vector store is optional."""

    class DegradedCheck:
        name = "vector_store"
        critical = False

        async def check(self) -> ComponentHealth:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="not provisioned",
            )

    from app.core.health import HealthRegistry

    registry = client._transport.app.state.container.resolve(HealthRegistry)  # type: ignore[union-attr]
    registry.register(DegradedCheck())

    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == HealthStatus.DEGRADED.value


async def test_correlation_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={CORRELATION_HEADER: "trace-me-123"})

    assert response.headers[CORRELATION_HEADER] == "trace-me-123"


async def test_correlation_id_is_generated_when_absent(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.headers.get(CORRELATION_HEADER)
