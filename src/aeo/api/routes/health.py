"""Liveness/readiness endpoint with config sanity (PRD §8)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aeo import __app_name__, __version__
from aeo.api.deps import SettingsDep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    openrouter_key_present: bool
    orchestrator_model: str
    target_panel_size: int


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=__app_name__,
        version=__version__,
        openrouter_key_present=settings.has_api_key,
        orchestrator_model=settings.orchestrator_model,
        target_panel_size=len(settings.target_models),
    )
