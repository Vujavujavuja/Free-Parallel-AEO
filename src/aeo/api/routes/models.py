"""Model catalog endpoint (PRD §8)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aeo.api.deps import SettingsDep
from aeo.exceptions import ProviderError
from aeo.providers import ModelInfo, get_provider

router = APIRouter(tags=["models"])


@router.get("/models", response_model=list[ModelInfo])
async def list_models(settings: SettingsDep, stub: bool = False) -> list[ModelInfo]:
    provider = get_provider("stub" if stub else "openrouter", settings)
    try:
        return await provider.list_models()
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await provider.aclose()
