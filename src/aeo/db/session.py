"""Database engine and session factories (async app + sync utility)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from aeo.settings import Settings, get_settings

_async_engine: AsyncEngine | None = None
_async_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory for a file-based SQLite DB if needed."""
    marker = ":///"
    if url.startswith("sqlite") and marker in url:
        raw = url.split(marker, 1)[1]
        if raw and raw != ":memory:":
            Path(raw).parent.mkdir(parents=True, exist_ok=True)


def get_async_engine(settings: Settings | None = None) -> AsyncEngine:
    global _async_engine, _async_sessionmaker
    if _async_engine is None:
        settings = settings or get_settings()
        _ensure_sqlite_dir(settings.database_url)
        _async_engine = create_async_engine(
            settings.async_database_url, future=True, echo=False
        )
        _async_sessionmaker = async_sessionmaker(
            _async_engine, expire_on_commit=False, class_=AsyncSession
        )
    return _async_engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _async_sessionmaker is None:
        get_async_engine()
    assert _async_sessionmaker is not None
    return _async_sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async session."""
    async with get_sessionmaker()() as session:
        yield session


def sync_session(settings: Settings | None = None) -> Session:
    """Create a synchronous session (used by CLI / bootstrap utilities)."""
    settings = settings or get_settings()
    _ensure_sqlite_dir(settings.database_url)
    engine = create_engine(settings.database_url, future=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    return factory()
