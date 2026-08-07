"""Health check for the shared organizational memory.

Registers into the health registry established in Milestone 0. That registry was
built to accept checks without modification, and this is the first proof: the
readiness endpoint and the workspace status panel both pick up the database with
no change to either.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.health import ComponentHealth, HealthStatus
from app.db.models import ProjectRow
from app.db.session import Database


class DatabaseHealthCheck:
    """Verifies the shared memory is reachable and its schema is present.

    Deliberately issues a real query against a real table rather than
    ``SELECT 1``. A connection can be alive while the schema is missing — the
    exact state after a failed migration — and that must read as unhealthy.
    """

    def __init__(self, database: Database) -> None:
        self._db = database

    @property
    def name(self) -> str:
        return "shared_memory"

    @property
    def critical(self) -> bool:
        """Critical: without memory there is no source of truth to reason over."""
        return True

    async def check(self) -> ComponentHealth:
        async with self._db.session() as session:
            result = await session.execute(select(ProjectRow.id).limit(1))
            result.first()

        return ComponentHealth(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message="Schema reachable",
        )
