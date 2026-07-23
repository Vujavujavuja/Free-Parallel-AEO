"""Trend tracking: group a company's runs over time and expose key metrics per
run so mention/provenance/share-of-voice trends can be charted (AI-mentions
report requirement)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from aeo.constants import RunStatus
from aeo.storage import RunStore


class TrendPoint(BaseModel):
    run_id: str
    created_at: str
    brand_mentions: int
    models_mentioning: int
    models_total: int
    organic: int
    search_driven: int
    absent: int
    top_competitor: str
    top_competitor_count: int
    cost_usd: float


class CompanyTrend(BaseModel):
    company: str
    runs: int
    points: list[TrendPoint]


def _point(data: dict[str, Any]) -> TrendPoint | None:
    analysis = data.get("analysis")
    if not analysis:
        return None
    models = analysis.get("models", [])
    prov = {"organic": 0, "search_driven": 0, "absent": 0}
    comp_totals: dict[str, int] = {}
    brand_total = 0
    mentioning = 0
    for m in models:
        brand_total += m.get("brand_mentions", 0)
        if m.get("brand_mentions", 0) > 0:
            mentioning += 1
        prov[m.get("provenance", "absent")] = prov.get(m.get("provenance", "absent"), 0) + 1
        for c, v in (m.get("competitor_totals") or {}).items():
            comp_totals[c] = comp_totals.get(c, 0) + v
    top = max(comp_totals.items(), key=lambda kv: kv[1], default=("", 0))
    return TrendPoint(
        run_id=data["id"],
        created_at=str(data.get("created_at", "")),
        brand_mentions=brand_total,
        models_mentioning=mentioning,
        models_total=len(models),
        organic=prov["organic"],
        search_driven=prov["search_driven"],
        absent=prov["absent"],
        top_competitor=top[0],
        top_competitor_count=top[1],
        cost_usd=round(data.get("total_cost_usd", 0.0), 4),
    )


def company_trends(store: RunStore | None = None) -> list[CompanyTrend]:
    """Group completed runs by company name; return chronological trend points."""
    store = store or RunStore.from_settings()
    grouped: dict[str, list[TrendPoint]] = {}
    display: dict[str, str] = {}
    for data in store.list_runs():
        if data.get("status") != RunStatus.COMPLETED.value:
            continue
        name = data.get("company", {}).get("name", "").strip()
        if not name:
            continue
        pt = _point(data)
        if pt is None:
            continue
        key = name.lower()
        display.setdefault(key, name)
        grouped.setdefault(key, []).append(pt)

    trends: list[CompanyTrend] = []
    for key, points in grouped.items():
        points.sort(key=lambda p: p.created_at)
        trends.append(CompanyTrend(company=display[key], runs=len(points), points=points))
    trends.sort(key=lambda t: t.runs, reverse=True)
    return trends
