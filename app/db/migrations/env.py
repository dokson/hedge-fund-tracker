"""
Alembic environment for async SQLAlchemy.

Reads the database URL from `app.db.session.DATABASE_URL` (which itself reads
`DATABASE_URL` env var) — never from `alembic.ini`, so credentials don't get
committed.

Importing `app.db.models` here ensures `Base.metadata` is fully populated
before autogenerate runs.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

# Make sure all models are imported so Base.metadata is complete.
from app.db import models  # noqa: F401
from app.db.session import DATABASE_URL, Base, make_engine

# Alembic Config object — provides access to the values within alembic.ini.
config = context.config

# Configure Python logging from the [loggers]/[handlers] sections of alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — emits SQL to stdout instead of running
    against a live DB. Useful for generating SQL scripts to apply manually.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Sync helper invoked by `connection.run_sync(...)` from the async runner.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Build a temporary async engine, run migrations, dispose the engine.
    Separate from app/db/session.py's module-level engine so `alembic upgrade`
    doesn't share connections with a running app process.
    """
    connectable = make_engine(DATABASE_URL, poolclass=None)
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """
    Entry point for online (live-DB) migration runs.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
