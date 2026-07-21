"""Shared FastAPI dependencies: DB session and optional bearer-token auth."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from aeo.db.session import get_session
from aeo.settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(db_session)]


async def require_auth(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Enforce the optional API_TOKEN bearer guard when configured."""
    if settings.api_token is None:
        return
    expected = settings.api_token.get_secret_value()
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


AuthGuard = Annotated[None, Depends(require_auth)]
