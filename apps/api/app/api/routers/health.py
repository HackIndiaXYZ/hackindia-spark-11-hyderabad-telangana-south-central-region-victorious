"""Health and readiness endpoints.

Mounted outside the versioned API prefix: orchestrators and load balancers should
not have to track the API version to probe the service.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import HealthRegistryDep, SettingsDep
from app.core.health import HealthReport, HealthStatus

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    response_model=dict[str, str],
)
async def health(settings: SettingsDep) -> dict[str, str]:
    """Report that the process is alive.

    Deliberately checks nothing external. A liveness probe that fails when a
    dependency is down causes restart loops that make an outage worse.
    """
    return {
        "status": HealthStatus.HEALTHY.value,
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment.value,
    }


@router.get(
    "/health/ready",
    summary="Readiness probe",
    response_model=HealthReport,
    responses={503: {"description": "One or more critical components are unavailable."}},
)
async def readiness(
    registry: HealthRegistryDep,
    settings: SettingsDep,
    response: Response,
) -> HealthReport:
    """Report whether every critical dependency is usable.

    Returns 503 when unhealthy so orchestrators drain traffic; a degraded system
    still returns 200, because partial capability beats no capability.
    """
    report = await registry.evaluate(
        version=settings.version,
        environment=settings.environment.value,
    )

    if not report.is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return report
