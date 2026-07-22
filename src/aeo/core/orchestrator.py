"""Orchestrator: turn a company profile into a structured question set using a
JSON-schema-constrained model call (PRD FR-4..FR-6, Appendix B, D)."""

from __future__ import annotations

import json
import re
from typing import Any

from aeo.core.prompting import DEFAULT_CATEGORIES, render_orchestrator
from aeo.exceptions import OrchestratorError
from aeo.providers.base import ChatMessage, LLMProvider
from aeo.schemas.company import CompanyProfile, SourceDocument
from aeo.schemas.question import Question, QuestionSet

_ORCHESTRATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions", "competitors", "brand_aliases"],
    "additionalProperties": False,
    "properties": {
        "competitors": {"type": "array", "items": {"type": "string"}},
        "brand_aliases": {"type": "array", "items": {"type": "string"}},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["index", "category", "text", "intent", "expected_source_types"],
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "category": {"type": "string"},
                    "text": {"type": "string"},
                    "intent": {"type": "string"},
                    "expected_source_types": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

_SYSTEM = ChatMessage(
    role="system",
    content="You output only valid JSON that conforms to the requested schema.",
)


async def generate_questions(
    provider: LLMProvider,
    company: CompanyProfile,
    *,
    model: str,
    question_count: int = 10,
    max_tokens: int = 4000,
    categories: list[str] | None = None,
    documents: list[SourceDocument] | None = None,
    existing_questions: list[str] | None = None,
) -> QuestionSet:
    """Call the orchestrator model and parse its structured question set."""
    prompt = render_orchestrator(
        company, question_count, categories or DEFAULT_CATEGORIES,
        documents=documents, existing_questions=existing_questions,
    )
    result = await provider.chat(
        model,
        [_SYSTEM, ChatMessage(role="user", content=prompt)],
        max_tokens=max_tokens,
        temperature=0.4,
        response_schema=_ORCHESTRATOR_SCHEMA,
    )
    data = _parse_json(result.content)
    try:
        question_set = QuestionSet.model_validate(data)
    except Exception as exc:
        raise OrchestratorError(f"Orchestrator returned an invalid question set: {exc}") from exc

    if not question_set.questions:
        raise OrchestratorError("Orchestrator returned no questions.")
    # Normalize indices to 1..N in case the model numbered them oddly.
    question_set.questions = [
        Question(
            index=i + 1,
            category=q.category,
            text=q.text,
            intent=q.intent,
            expected_source_types=q.expected_source_types,
        )
        for i, q in enumerate(question_set.questions)
    ]
    return question_set


def _parse_json(content: str) -> dict[str, Any]:
    content = content.strip()
    try:
        parsed: dict[str, Any] = json.loads(content)
        return parsed
    except json.JSONDecodeError:
        pass
    # Fallback: extract the first {...} block (models sometimes wrap JSON in prose).
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed
        except json.JSONDecodeError as exc:
            raise OrchestratorError(f"Could not parse orchestrator JSON: {exc}") from exc
    raise OrchestratorError("Orchestrator response contained no JSON object.")
