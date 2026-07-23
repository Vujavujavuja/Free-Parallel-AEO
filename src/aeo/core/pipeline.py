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
from aeo.core import orchestrator, runner, synthesizer
from aeo.logging import get_logger
from aeo.providers.base import LLMProvider
from aeo.providers.stub import StubProvider
from aeo.schemas.question import Question
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
    log: str | None = None  # a detailed end-to-end log line, if this event carries one


EmitCb = Callable[[ProgressEvent], Awaitable[None]] | None
ReportFn = Callable[[RunRecord], dict[str, str]] | None


async def _emit_log(record: RunRecord, emit: EmitCb, message: str) -> None:
    """Append a timestamped line to the run's log and stream it live."""
    line = f"{utcnow().strftime('%H:%M:%S')}  {message}"
    record.logs.append(line)
    if emit:
        await emit(ProgressEvent(run_id=record.id, status=record.status, log=line))


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
        # 1. Questions (custom exact questions + orchestrator-generated remainder)
        await _set(RunStatus.GENERATING_QUESTIONS, "Generating buyer questions")
        await _emit_log(record, emit, f"Run started for {record.company.name}.")
        custom = [q.strip() for q in record.options.custom_questions if q.strip()]
        needed = max(0, record.options.question_count - len(custom))
        if needed > 0:
            await _emit_log(
                record, emit,
                f"Orchestrator ({record.options.orchestrator_model}) generating "
                f"{needed} questions ({len(custom)} custom supplied)…",
            )

        generated: list[Question] = []
        gen_competitors: list[str] = []
        gen_aliases: list[str] = []
        if needed > 0:
            question_set = await orchestrator.generate_questions(
                provider, record.company,
                model=record.options.orchestrator_model,
                question_count=needed,
                documents=record.company.source_documents,
                existing_questions=custom,
                language=record.options.language,
            )
            generated = question_set.questions
            gen_competitors = question_set.competitors
            gen_aliases = question_set.brand_aliases
            # Fill any profile fields the user left blank from the orchestrator's
            # inference (name/website/documents). Never overwrites provided values.
            filled = orchestrator.enrich_company(record.company, question_set.inferred)
            if filled:
                await _emit_log(
                    record, emit,
                    f"Orchestrator inferred blank fields from name/site: {', '.join(filled)}.",
                )

        custom_qs = [
            Question(index=0, category="custom", text=t, intent="user-provided")
            for t in custom
        ]
        merged_questions = custom_qs + generated
        record.questions = [
            q.model_copy(update={"index": i + 1})
            for i, q in enumerate(merged_questions)
        ]
        record.competitors = _merge(record.company.competitors, gen_competitors)
        record.brand_aliases = _merge(record.company.aliases, gen_aliases)
        record.company.aliases = record.brand_aliases
        await _emit_log(
            record, emit,
            f"{len(record.questions)} questions ready; "
            f"{len(record.competitors)} competitors, {len(record.brand_aliases)} brand aliases.",
        )
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
        await _emit_log(
            record, emit,
            f"Querying {n_models} models"
            f"{' with web search' if record.options.enable_web_search else ''} "
            f"(concurrency {record.options.concurrency}, cap ${record.options.cost_cap_usd:.2f})…",
        )

        async def on_progress(done: int, total: int, model: str) -> None:
            if emit:
                await emit(
                    ProgressEvent(
                        run_id=record.id, status=RunStatus.RUNNING_MODELS,
                        detail=f"{model} done", completed=done, total=total,
                    )
                )

        async def on_log(line: str) -> None:
            await _emit_log(record, emit, line)

        # The neutral prompt carries no brand/competitor info, so give the stub
        # provider that context out-of-band for realistic offline demos.
        if isinstance(provider, StubProvider):
            provider.configure(record.company.brand_terms, record.competitors)

        brand = record.company.name if record.options.mention_brand else None
        record.responses = await runner.run_models(
            provider, record.questions, record.options,
            on_progress=on_progress, log_cb=on_log, brand=brand,
        )
        record.total_cost_usd = round(sum(r.cost_usd for r in record.responses), 6)
        failed = sum(1 for r in record.responses if r.error)
        await _emit_log(
            record, emit,
            f"Fan-out complete: {len(record.responses) - failed}/{len(record.responses)} "
            f"succeeded, ${record.total_cost_usd:.4f} spent.",
        )
        store.save_run(record.model_dump(mode="json"))

        # 3. Analysis (+ optional AI synthesis pass)
        await _set(RunStatus.ANALYZING, "Analyzing answers")
        result = analyze(record)
        mentioning = sum(1 for m in result.models if m.brand_mentions > 0)
        total_mentions = sum(m.brand_mentions for m in result.models)
        await _emit_log(
            record, emit,
            f"Analysis: {total_mentions} brand mentions; {mentioning}/{len(result.models)} "
            f"models mention {record.company.name}; {len(result.domain_frequency)} cited domains.",
        )
        if record.options.enable_ai_insights:
            await _set(RunStatus.ANALYZING, "Writing AI insights")
            await _emit_log(record, emit, "Synthesizing AI insights & quotes…")
            synth = await synthesizer.synthesize(
                provider, record.options.orchestrator_model,
                record.company, result, record.responses,
            )
            if synth:
                synthesizer.apply_synthesis(result, synth)
                await _emit_log(
                    record, emit, f"AI insights written ({len(result.insights)} findings)."
                )
        record.analysis = result.model_dump(mode="json")
        store.save_run(record.model_dump(mode="json"))

        # 4. Reports
        await _set(RunStatus.REPORTING, "Generating reports")
        await _emit_log(record, emit, "Rendering reports (xlsx, csv, json, pdf)…")
        if report_fn is not None:
            record.reports = report_fn(record)
            await _emit_log(record, emit, f"Reports ready: {', '.join(record.reports)}.")

        # 5. Done
        record.completed_at = utcnow()
        await _emit_log(record, emit, f"Completed. Total cost ${record.total_cost_usd:.4f}.")
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
