"""Trends endpoint — mention/provenance/SoV trends grouped by company."""

from __future__ import annotations

from fastapi import APIRouter

from aeo.api.deps import SettingsDep
from aeo.services.trend_service import CompanyTrend, company_trends
from aeo.storage import RunStore

router = APIRouter(tags=["trends"])


@router.get("/trends", response_model=list[CompanyTrend])
async def trends(settings: SettingsDep) -> list[CompanyTrend]:
    return company_trends(RunStore.from_settings(settings))
