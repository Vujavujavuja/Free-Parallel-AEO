"""Runtime settings endpoint — set the OpenRouter API key from the UI.

The key is validated against OpenRouter, stored in the local ``.env`` and the
in-memory settings, and never returned to the client (only a presence flag).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aeo.api.deps import AuthGuard, SettingsDep
from aeo.settings import update_openrouter_key

router = APIRouter(tags=["settings"])


class OpenRouterKeyRequest(BaseModel):
    key: str = Field(min_length=1)


class KeyStatus(BaseModel):
    key_present: bool


@router.get("/settings/openrouter-key", response_model=KeyStatus)
async def key_status(settings: SettingsDep) -> KeyStatus:
    return KeyStatus(key_present=settings.has_api_key)


@router.put("/settings/openrouter-key", response_model=KeyStatus)
async def set_key(
    body: OpenRouterKeyRequest, settings: SettingsDep, _auth: AuthGuard
) -> KeyStatus:
    key = body.key.strip()
    # Validate against OpenRouter; reject only on an explicit auth failure so a
    # transient network error doesn't block a valid key.
    try:
        async with httpx.AsyncClient(
            base_url=settings.openrouter_base_url, timeout=15.0
        ) as client:
            resp = await client.get(
                "/auth/key", headers={"Authorization": f"Bearer {key}"}
            )
        if resp.status_code in (401, 403):
            raise HTTPException(status_code=400, detail="OpenRouter rejected this key.")
    except httpx.HTTPError:
        pass  # network hiccup — accept; model loading will surface a bad key

    update_openrouter_key(key)
    return KeyStatus(key_present=True)
