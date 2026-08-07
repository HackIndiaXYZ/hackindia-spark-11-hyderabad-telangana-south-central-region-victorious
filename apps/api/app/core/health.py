"""Component health checking.

Liveness and readiness are answered separately, because they mean different
things to an orchestrator: liveness failing means *restart me*, readiness failing
means *stop sending me traffic until my dependencies recover*.

Readiness is assembled from a registry of ``HealthCheck`` implementations. Each
later milestone contributes its own check — the memory repository in Milestone 1,
the LLM providers in Milestone 2 — without this module changing. That is the
extensibility requirement applied to observability rather than only to agents.
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# A slow dependency must not turn a readiness probe into a hanging request.
_CHECK_TIMEOUT_SECONDS = 5.0


class HealthStatus(StrEnum):
    """Health of a single component or of the system as a whole."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Result of checking one component."""

    name: str
    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)


@runtime_checkable
class HealthCheck(Protocol):
    """A dependency that can report whether it is usable.

    Implementations must not raise: a check that throws is treated as unhealthy,
    but returning a descriptive ``ComponentHealth`` produces a far better
    operator experience than an exception trace.
    """

    @property
    def name(self) -> str:
        """Stable component identifier, e.g. ``"database"``."""
        ...

    @property
    def critical(self) -> bool:
        """Whether failure makes the whole system unready.

        Non-critical failures degrade rather than fail readiness — the vector
        store being down should not take the platform offline.
        """
        ...

    async def check(self) -> ComponentHealth:
        """Probe the component and describe its state."""
        ...


class HealthReport(BaseModel):
    """Aggregate readiness across every registered component."""

    status: HealthStatus
    version: str
    environment: str
    components: list[ComponentHealth] = Field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """Degraded still serves traffic; unhealthy does not."""
        return self.status is not HealthStatus.UNHEALTHY


class HealthRegistry:
    """Collects health checks and evaluates them concurrently."""

    def __init__(self) -> None:
        self._checks: list[HealthCheck] = []

    def register(self, check: HealthCheck) -> None:
        """Add a component check to the readiness probe."""
        self._checks.append(check)
        logger.debug("Registered health check", extra={"component": check.name})

    async def evaluate(self, *, version: str, environment: str) -> HealthReport:
        """Run every check concurrently and aggregate the outcome.

        Concurrency matters: readiness probes are polled frequently, and running
        N checks in series would multiply probe latency by N.
        """
        results = await asyncio.gather(
            *(self._run_one(check) for check in self._checks),
            return_exceptions=False,
        )

        critical_by_name = {check.name: check.critical for check in self._checks}
        overall = HealthStatus.HEALTHY

        for result in results:
            if result.status is HealthStatus.HEALTHY:
                continue
            if critical_by_name.get(result.name, True) and result.status is HealthStatus.UNHEALTHY:
                overall = HealthStatus.UNHEALTHY
                break
            overall = HealthStatus.DEGRADED

        return HealthReport(
            status=overall,
            version=version,
            environment=environment,
            components=list(results),
        )

    async def _run_one(self, check: HealthCheck) -> ComponentHealth:
        """Execute one check under a timeout, converting failures into results."""
        started = time.perf_counter()
        try:
            async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
                result = await check.check()
            if result.latency_ms is None:
                result = result.model_copy(
                    update={"latency_ms": (time.perf_counter() - started) * 1000}
                )
            return result
        except TimeoutError:
            return ComponentHealth(
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check exceeded {_CHECK_TIMEOUT_SECONDS:.0f}s",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        # Broad by design: a health probe reports failure, it never propagates it.
        except Exception as exc:
            logger.exception("Health check raised", extra={"component": check.name})
            return ComponentHealth(
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"{type(exc).__name__}: {exc}",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
