"""Run schemas: options, per-model response records, and the full run record
that is serialized to ``run.json`` (PRD §7, adapted for filesystem storage)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from aeo.constants import PromptMode, RunStatus
from aeo.schemas.company import CompanyProfile
from aeo.schemas.question import Question


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(UTC)


class RunOptions(BaseModel):
    orchestrator_model: str
    target_models: list[str]
    provider: str = "openrouter"  # "openrouter" | "stub"
    question_count: int = 10
    prompt_mode: PromptMode = PromptMode.SINGLE_SHOT
    enable_web_search: bool = False
    max_tokens: int = 8000
    concurrency: int = 6
    cost_cap_usd: float = 5.0
    auto_approve_questions: bool = True
    max_continuations: int = 4
    enable_ai_insights: bool = True  # LLM synthesis pass for interpretations/quotes
    # Exact questions supplied by the user; included verbatim in the run.
    custom_questions: list[str] = Field(default_factory=list)


class ModelResponseRecord(BaseModel):
    """One model's answer. For single-shot, ``question_index`` is None (whole
    answer covers all questions); for per-question mode it is set."""

    model_id: str
    question_index: int | None = None
    content: str = ""
    finish_reason: str | None = None
    web_search_used: bool = False
    search_queries: list[str] = Field(default_factory=list)
    search_citations: list[str] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    continuations: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.content)


class RunRecord(BaseModel):
    """The complete, self-contained record persisted as ``run.json``."""

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.CREATED
    stage_detail: str | None = None

    company: CompanyProfile
    options: RunOptions

    questions: list[Question] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    brand_aliases: list[str] = Field(default_factory=list)

    responses: list[ModelResponseRecord] = Field(default_factory=list)
    analysis: dict[str, Any] | None = None

    total_cost_usd: float = 0.0
    error: str | None = None
    reports: dict[str, str] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)  # human-readable end-to-end log lines

    def summary(self) -> RunSummary:
        return RunSummary(
            id=self.id,
            created_at=self.created_at,
            status=self.status,
            company_name=self.company.name,
            total_cost_usd=self.total_cost_usd,
            num_models=len(self.options.target_models),
            num_questions=len(self.questions),
        )


class RunSummary(BaseModel):
    id: str
    created_at: datetime
    status: RunStatus
    company_name: str
    total_cost_usd: float
    num_models: int
    num_questions: int
