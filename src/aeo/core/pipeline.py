"""Run pipeline state machine (PRD §4.1).

CREATED -> GENERATING_QUESTIONS -> [AWAITING_APPROVAL] -> RUNNING_MODELS
       -> ANALYZING -> REPORTING -> COMPLETED   (FAILED reachable from any stage)

Each stage is checkpointed to ``run.json`` so a crashed run is inspectable, and
progress is emitted via an async callback that the CLI logs and the SSE endpoint
streams. Report generation is injected so this module stays free of the heavy
reporting/openpyxl dependencies.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from aeo.analysis import analyze
from aeo.constants import RunStatus
from aeo.core import orchestrator, runner
from aeo.logging import get_logger
from aeo.providers.base import LLMProvider
from aeo.schemas.run import RunRecord
from aeo.storage import RunStore
from aeo.utils import utcnow

log = get_logger(__name__)


class ProgressEvent(BaseModel):
    run_id: str
    status: RunStatus
    detail: str = ""
    completed: int = 0
    total: int = 0


EmitCb = Callable[[ProgressEvent], Awaitable[None]] | None
ReportFn = Callable[[RunRecord], dict[str, str]] | None


async def execute_pipeline(
    record: RunRecord,
    provider: LLMProvider,
    store: RunStore,
    *,
    emit: EmitCb = None,
    report_fn: ReportFn = None,
    stop_for_approval: bool = False,
) -> RunRecord:
    """Run the full pipeline. If ``stop_for_approval`` and questions are not
    auto-approved, halt at AWAITING_APPROVAL after generating questions."""

    async def _set(status: RunStatus, detail: str = "", completed: int = 0, total: int = 0) -> None:
        record.status = status
        record.stage_detail = detail or None
        store.save_run(record.model_dump(mode="json"))
        if emit:
            await emit(
                ProgressEvent(
                    run_id=record.id, status=status, detail=detail,
                    completed=completed, total=total,
                )
            )

    try:
        # 1. Questions
        await _set(RunStatus.GENERATING_QUESTIONS, "Generating buyer questions")
        question_set = await orchestrator.generate_questions(
            provider, record.company,
            model=record.options.orchestrator_model,
            question_count=record.options.question_count,
        )
        record.questions = question_set.questions
        record.competitors = _merge(record.company.competitors, question_set.competitors)
        record.brand_aliases = _merge(record.company.aliases, question_set.brand_aliases)
        record.company.aliases = record.brand_aliases
        store.save_run(record.model_dump(mode="json"))

        if stop_for_approval and not record.options.auto_approve_questions:
            await _set(RunStatus.AWAITING_APPROVAL, "Awaiting question approval")
            return record

        return await resume_after_questions(
            record, provider, store, emit=emit, report_fn=report_fn
        )
    except Exception as exc:
        return await _fail(record, store, emit, exc)


async def resume_after_questions(
    record: RunRecord,
    provider: LLMProvider,
    store: RunStore,
    *,
    emit: EmitCb = None,
    report_fn: ReportFn = None,
) -> RunRecord:
    """Continue from the model fan-out (used after a manual approval gate too)."""

    async def _set(status: RunStatus, detail: str = "", completed: int = 0, total: int = 0) -> None:
        record.status = status
        record.stage_detail = detail or None
        store.save_run(record.model_dump(mode="json"))
        if emit:
            await emit(
                ProgressEvent(
                    run_id=record.id, status=status, detail=detail,
                    completed=completed, total=total,
                )
            )

    try:
        # 2. Fan-out
        n_models = len(record.options.target_models)
        await _set(RunStatus.RUNNING_MODELS, "Querying models", 0, n_models)

        async def on_progress(done: int, total: int, model: str) -> None:
            if emit:
                await emit(
                    ProgressEvent(
                        run_id=record.id, status=RunStatus.RUNNING_MODELS,
                        detail=f"{model} done", completed=done, total=total,
                    )
                )

        record.responses = await runner.run_models(
            provider, record.company, record.questions, record.competitors,
            record.options, on_progress=on_progress,
        )
        record.total_cost_usd = round(sum(r.cost_usd for r in record.responses), 6)
        store.save_run(record.model_dump(mode="json"))

        # 3. Analysis
        await _set(RunStatus.ANALYZING, "Analyzing answers")
        result = analyze(record)
        record.analysis = result.model_dump(mode="json")
        store.save_run(record.model_dump(mode="json"))

        # 4. Reports
        await _set(RunStatus.REPORTING, "Generating reports")
        if report_fn is not None:
            record.reports = report_fn(record)

        # 5. Done
        record.completed_at = utcnow()
        await _set(RunStatus.COMPLETED, "Completed")
        return record
    except Exception as exc:
        return await _fail(record, store, emit, exc)


async def _fail(
    record: RunRecord, store: RunStore, emit: EmitCb, exc: Exception
) -> RunRecord:
    record.status = RunStatus.FAILED
    record.error = f"{type(exc).__name__}: {exc}"
    record.completed_at = utcnow()
    store.save_run(record.model_dump(mode="json"))
    log.error("pipeline_failed", run_id=record.id, error=record.error)
    if emit:
        await emit(
            ProgressEvent(run_id=record.id, status=RunStatus.FAILED, detail=record.error)
        )
    return record


def _merge(base: list[str], extra: list[str]) -> list[str]:
    merged = list(base)
    lowered = {x.lower() for x in merged}
    for item in extra:
        if item and item.lower() not in lowered:
            merged.append(item)
            lowered.add(item.lower())
    return merged
