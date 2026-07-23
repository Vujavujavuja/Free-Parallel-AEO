"""Aggregate API router."""

from __future__ import annotations

from fastapi import APIRouter

from aeo.api.routes import documents, health, models, runs, settings, trends

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(settings.router)
api_router.include_router(models.router)
api_router.include_router(documents.router)
api_router.include_router(runs.router)
api_router.include_router(trends.router)
