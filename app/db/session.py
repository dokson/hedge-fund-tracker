"""
Async SQLAlchemy engine + session factory.

Single source of truth for the Postgres connection. The URL is read from the
DATABASE_URL env var so the same code runs locally (developer machine) and in
deployed environments (single-VM Docker, Fly, Railway, ...).

Connection format expected:
    postgresql+asyncpg://user:password@host:port/dbname
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    # Sensible local default for `docker compose up` of the postgres service.
    # Override in deploy environments.
    "postgresql+asyncpg://hft:hft@localhost:5432/hft",
)


class Base(DeclarativeBase):
    """
    Declarative base for all ORM models. Imported by every model module.
    Alembic's env.py imports `Base.metadata` to autogenerate migrations.
    """


def make_engine(url: str = DATABASE_URL, **kwargs) -> AsyncEngine:
    """
    Build the async engine. Pool sizes are conservative defaults suitable for a
    single-VM deployment; tune via env vars if needed.
    """
    return create_async_engine(
        url,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        pool_pre_ping=True,
        **kwargs,
    )


engine: AsyncEngine = make_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency for request-scoped sessions:

        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
