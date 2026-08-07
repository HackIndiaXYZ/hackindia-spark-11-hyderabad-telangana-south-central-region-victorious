"""Application entry point.

Assembles the FastAPI application from independently testable pieces. The factory
takes optional settings so tests can build an app against any configuration
without touching the environment.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health as health_router
from app.api.routers import projects
from app.core.bootstrap import build_container
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import AccessLogMiddleware, CorrelationMiddleware
from app.db.session import Database

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Configuration override. Defaults to the process settings.

    Returns:
        A fully wired FastAPI application.
    """
    resolved = settings or get_settings()
    configure_logging(resolved.observability)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Own the container's lifetime.

        Built before the first request and disposed after the last, so database
        engines and provider clients are released deterministically.
        """
        app.state.container = build_container(resolved)
        logger.info(
            "%s starting", resolved.app_name,
            extra={"version": resolved.version, "environment": resolved.environment.value},
        )

        # Outside production, create any missing tables so a fresh checkout runs
        # with no setup step. Production schema evolution belongs to Alembic —
        # create_all cannot express a migration, only an initial shape.
        if not resolved.is_production:
            await app.state.container.resolve(Database).create_schema()

        try:
            yield
        finally:
            await app.state.container.aclose()
            logger.info("%s stopped", resolved.app_name)

    app = FastAPI(
        title=resolved.app_name,
        version=resolved.version,
        description=(
            "AI-native Software Engineering Organization. Coordinates specialized "
            "engineering agents across the software lifecycle with shared memory, "
            "full traceability, and human approval gates."
        ),
        docs_url=resolved.docs_url,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Order matters: middleware added last runs first, so correlation IDs are
    # bound before the access log tries to read one.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    register_exception_handlers(app)

    app.include_router(health_router.router)
    app.include_router(projects.router, prefix=resolved.api_prefix)
    app.include_router(projects.approvals_router, prefix=resolved.api_prefix)

    return app


app = create_app()
