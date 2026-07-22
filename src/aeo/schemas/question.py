"""Question + orchestrator-output schemas (PRD FR-4..FR-6, Appendix B)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Question(BaseModel):
    index: int
    category: str = "general"
    text: str
    intent: str | None = None
    expected_source_types: list[str] = Field(default_factory=list)


class QuestionSet(BaseModel):
    """Structured orchestrator output: questions + proposed competitors + aliases."""

    questions: list[Question]
    competitors: list[str] = Field(default_factory=list)
    brand_aliases: list[str] = Field(default_factory=list)
