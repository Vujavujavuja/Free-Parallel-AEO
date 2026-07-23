"""Run lifecycle endpoints incl. SSE progress (PRD §8)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from aeo.api.deps import AuthGuard, SettingsDep
from aeo.api.executor import get_broker, stream_closes_on
from aeo.core.pipeline import ProgressEvent
from aeo.providers import get_provider
from aeo.schemas.api import QuestionApproval, RunCreateRequest
from aeo.schemas.run import RunRecord, RunSummary
from aeo.services import run_service
from aeo.storage import RunStore

router = APIRouter(tags=["runs"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "json": "application/json",
    "pdf": "application/pdf",
    "md": "text/markdown",
}


@router.post("/runs", response_model=RunRecord, status_code=201)
async def create_run(
    req: RunCreateRequest, settings: SettingsDep, _auth: AuthGuard
) -> RunRecord:
    if req.provider == "openrouter" and not settings.has_api_key:
        raise HTTPException(
            status_code=400,
            detail="OPENROUTER_API_KEY is not set. Use provider='stub' or add the key.",
        )
    options = run_service.options_from_settings(settings, target_models=req.target_models)
    options.provider = req.provider
    for field in (
        "question_count", "prompt_mode", "enable_web_search",
        "max_tokens", "concurrency", "cost_cap_usd", "auto_approve_questions",
        "enable_ai_insights", "mention_brand",
    ):
        value = getattr(req, field)
        if value is not None:
            setattr(options, field, value)
    if req.custom_questions:
        options.custom_questions = [q for q in req.custom_questions if q.strip()]
    if req.provider == "stub" and not req.target_models:
        options.target_models = [
            "openai/gpt-stub", "anthropic/claude-stub", "google/gemini-stub",
            "meta/llama-stub", "mistral/mistral-stub",
        ]

    # Validate real model ids against the live catalog; drop invalid, keep valid.
    if req.provider == "openrouter":
        options.target_models = await _validate_models(options.target_models, settings)

    record = run_service.build_run(req.profile, options)
    store = RunStore.from_settings(settings)
    store.ensure()
    store.save_run(record.model_dump(mode="json"))
    get_broker().start(
        record, provider_name=req.provider, settings=settings, store=store
    )
    return record


async def _validate_models(target: list[str], settings: SettingsDep) -> list[str]:
    """Keep only model ids present in the live OpenRouter catalog."""
    provider = get_provider("openrouter", settings)
    try:
        catalog = {m.id for m in await provider.list_models()}
    finally:
        await provider.aclose()
    valid = [m for m in target if m in catalog]
    invalid = [m for m in target if m not in catalog]
    if not valid:
        raise HTTPException(
            status_code=400,
            detail=(
                "None of the selected models exist on OpenRouter"
                f"{f' (invalid: {invalid})' if invalid else ''}. "
                "Use 'Load catalog' in the form to pick valid model ids."
            ),
        )
    return valid


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(settings: SettingsDep) -> list[RunSummary]:
    return run_service.list_runs(RunStore.from_settings(settings))


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str, settings: SettingsDep) -> RunRecord:
    store = RunStore.from_settings(settings)
    if not store.exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    return run_service.get_run(run_id, store)


@router.post("/runs/{run_id}/questions/approve", response_model=RunRecord)
async def approve_questions(
    run_id: str, body: QuestionApproval, settings: SettingsDep, _auth: AuthGuard
) -> RunRecord:
    store = RunStore.from_settings(settings)
    if not store.exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    record = run_service.get_run(run_id, store)
    if body.questions:
        record.questions = body.questions
        store.save_run(record.model_dump(mode="json"))
    get_broker().resume(
        record, provider_name=record.options.provider, settings=settings, store=store
    )
    return record


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, settings: SettingsDep) -> EventSourceResponse:
    store = RunStore.from_settings(settings)
    broker = get_broker()

    async def generator() -> AsyncIterator[dict[str, str]]:
        queue = broker.subscribe(run_id)
        try:
            # Seed a terminal event for runs with no live history (e.g. after a
            # server restart) so the client isn't left hanging.
            if queue.empty() and not broker.is_running(run_id) and store.exists(run_id):
                rec = run_service.get_run(run_id, store)
                seed = ProgressEvent(
                    run_id=run_id, status=rec.status, detail=rec.stage_detail or ""
                )
                yield {"event": "progress", "data": seed.model_dump_json()}
                if stream_closes_on(rec.status):
                    return
            while True:
                event = await queue.get()
                yield {"event": "progress", "data": event.model_dump_json()}
                if stream_closes_on(event.status):
                    return
        finally:
            broker.unsubscribe(run_id, queue)

    return EventSourceResponse(generator())


@router.get("/runs/{run_id}/report")
async def download_report(
    run_id: str, settings: SettingsDep, format: str = "xlsx"
) -> FileResponse:
    store = RunStore.from_settings(settings)
    if not store.exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    record = run_service.get_run(run_id, store)
    path_str = record.reports.get(format)
    if not path_str or not Path(path_str).is_file():
        raise HTTPException(status_code=404, detail=f"No {format} report for this run.")
    return FileResponse(
        path_str,
        media_type=_MEDIA.get(format, "application/octet-stream"),
        filename=f"{record.company.name}-{run_id}.{format}".replace(" ", "_"),
    )


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: str, settings: SettingsDep, _auth: AuthGuard) -> None:
    store = RunStore.from_settings(settings)
    if not store.exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    store.delete_run(run_id)
