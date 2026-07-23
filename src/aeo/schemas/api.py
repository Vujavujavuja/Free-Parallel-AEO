"""Request/response DTOs specific to the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aeo.constants import PromptMode
from aeo.schemas.company import CompanyProfile
from aeo.schemas.question import Question


class RunCreateRequest(BaseModel):
    """Start a run from an inline company profile plus option overrides."""

    profile: CompanyProfile
    provider: Literal["openrouter", "stub"] = "openrouter"
    target_models: list[str] | None = None
    question_count: int | None = None
    prompt_mode: PromptMode | None = None
    enable_web_search: bool | None = None
    max_tokens: int | None = None
    concurrency: int | None = None
    cost_cap_usd: float | None = None
    auto_approve_questions: bool | None = None
    enable_ai_insights: bool | None = None
    custom_questions: list[str] | None = None


class QuestionApproval(BaseModel):
    """Approve (optionally edited) questions for a paused run."""

    questions: list[Question] | None = Field(
        default=None, description="If provided, replaces the generated questions."
    )
