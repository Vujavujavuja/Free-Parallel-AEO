"""Aggregate API router. Route modules are added here as milestones land."""

from __future__ import annotations

from fastapi import APIRouter

from aeo.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
