"""Alembic migration environment.

Reads the database URL from application settings rather than ``alembic.ini`` so
migrations always target the same database the application does — one source of
truth for the connection string, as for everything else.

Runs against the async engine directly, so the same driver (aiosqlite or asyncpg)
is exercised in migration as at runtime.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate compares the live database against this metadata.
target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database.url)


def _configure(connection: Connection) -> None:
    """Apply options shared by online and offline modes."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite cannot ALTER most columns; batch mode rewrites the table
        # instead, so the same migration script runs on SQLite and PostgreSQL
        # alike (ADR-0005).
        render_as_batch=connection.dialect.name == "sqlite",
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting.

    Used to hand a reviewable script to a DBA rather than applying changes
    directly to a production database.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Apply migrations against the configured database."""
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
