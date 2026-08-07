"""Database engine and session lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings
from app.core.logging import get_logger
from app.db.models import Base

logger = get_logger(__name__)


class Database:
    """Owns the engine and hands out sessions.

    Registered as a container singleton so the engine — and its connection pool —
    is created once per process and disposed on shutdown via ``aclose``.
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine = self._create_engine(settings)
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @staticmethod
    def _create_engine(settings: DatabaseSettings) -> AsyncEngine:
        """Build the engine, applying pooling only where it is meaningful.

        SQLite rejects pool sizing arguments; passing them raises rather than
        being ignored, so they are supplied only for server-backed dialects.
        """
        is_sqlite = settings.url.startswith("sqlite")

        if is_sqlite:
            return create_async_engine(settings.url, echo=settings.echo, future=True)

        return create_async_engine(
            settings.url,
            echo=settings.echo,
            future=True,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_pre_ping=True,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session inside a transaction.

        Commits on clean exit, rolls back on any exception. Callers therefore
        never manage transactions themselves, which is what makes a partially
        written artifact impossible: either the version row, the artifact update,
        and the trace edges all land, or none of them do.
        """
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_schema(self) -> None:
        """Create every table.

        For tests and first-run local development. Alembic owns schema evolution
        for anything long-lived — see ``app/db/migrations``.
        """
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("Database schema ensured")

    async def aclose(self) -> None:
        """Dispose the engine and its pool. Invoked by the container on shutdown."""
        await self._engine.dispose()
        logger.debug("Database engine disposed")
