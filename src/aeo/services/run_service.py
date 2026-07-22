"""Run orchestration service: build a run, execute the pipeline, persist, and
expose listing/lookup helpers (PRD FR-24)."""

from __future__ import annotations

from aeo.core import pipeline
from aeo.core.pipeline import EmitCb
from aeo.providers import get_provider
from aeo.schemas.company import CompanyProfile
from aeo.schemas.run import RunOptions, RunRecord, RunSummary
from aeo.services.report_service import generate_reports
from aeo.settings import Settings, get_settings
from aeo.storage import RunStore


def build_run(company: CompanyProfile, options: RunOptions) -> RunRecord:
    return RunRecord(company=company, options=options)


def options_from_settings(
    settings: Settings, target_models: list[str] | None = None
) -> RunOptions:
    return RunOptions(
        orchestrator_model=settings.orchestrator_model,
        target_models=target_models or list(settings.target_models),
        question_count=settings.question_count,
        prompt_mode=settings.prompt_mode,
        enable_web_search=settings.enable_web_search,
        max_tokens=settings.max_tokens,
        concurrency=settings.concurrency,
        cost_cap_usd=settings.cost_cap_usd,
        auto_approve_questions=settings.auto_approve_questions,
        max_continuations=settings.max_continuations,
    )


async def execute_run(
    record: RunRecord,
    *,
    provider_name: str = "openrouter",
    settings: Settings | None = None,
    store: RunStore | None = None,
    emit: EmitCb = None,
    stop_for_approval: bool = False,
) -> RunRecord:
    """Run the full pipeline for ``record`` and return the completed record."""
    settings = settings or get_settings()
    store = store or RunStore.from_settings(settings)
    store.ensure()
    store.save_run(record.model_dump(mode="json"))

    provider = get_provider(provider_name, settings)
    try:
        return await pipeline.execute_pipeline(
            record,
            provider,
            store,
            emit=emit,
            report_fn=lambda rec: generate_reports(rec, store),
            stop_for_approval=stop_for_approval,
        )
    finally:
        await provider.aclose()


async def resume_run(
    record: RunRecord,
    *,
    provider_name: str = "openrouter",
    settings: Settings | None = None,
    store: RunStore | None = None,
    emit: EmitCb = None,
) -> RunRecord:
    """Resume a run from the model fan-out (after a manual approval gate)."""
    settings = settings or get_settings()
    store = store or RunStore.from_settings(settings)
    provider = get_provider(provider_name, settings)
    try:
        return await pipeline.resume_after_questions(
            record,
            provider,
            store,
            emit=emit,
            report_fn=lambda rec: generate_reports(rec, store),
        )
    finally:
        await provider.aclose()


def list_runs(store: RunStore | None = None) -> list[RunSummary]:
    store = store or RunStore.from_settings()
    summaries: list[RunSummary] = []
    for data in store.list_runs():
        summaries.append(RunRecord.model_validate(data).summary())
    return summaries


def get_run(run_id: str, store: RunStore | None = None) -> RunRecord:
    store = store or RunStore.from_settings()
    return RunRecord.model_validate(store.load_run(run_id))
