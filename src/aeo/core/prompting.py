"""Jinja rendering for orchestrator and answer prompts."""

from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aeo.constants import PACKAGE_ROOT
from aeo.schemas.company import CompanyProfile, SourceDocument
from aeo.schemas.question import Question

_PROMPTS_DIR = PACKAGE_ROOT / "core" / "prompts"
_DOC_CHAR_CAP = 6000  # per-document truncation to keep the orchestrator prompt bounded

DEFAULT_CATEGORIES = [
    "need", "approaches", "differentiation", "evaluation_criteria", "pricing",
    "results_roi", "regulated_fit", "onboarding", "risks", "testimonials",
]


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_orchestrator(
    company: CompanyProfile,
    question_count: int,
    categories: list[str] | None = None,
    documents: list[SourceDocument] | None = None,
    existing_questions: list[str] | None = None,
) -> str:
    docs = [
        SourceDocument(name=d.name, text=d.text[:_DOC_CHAR_CAP])
        for d in (documents or [])
    ]
    return _env().get_template("orchestrator.jinja").render(
        company=company,
        question_count=question_count,
        categories=categories or DEFAULT_CATEGORIES,
        documents=docs,
        existing_questions=existing_questions or [],
    )


def render_answer(questions: list[Question], enable_web_search: bool = False) -> str:
    """Render the NEUTRAL answer prompt. It contains only the questions and
    neutral instructions — no company or competitor names — so brand mentions
    measured downstream are genuinely organic."""
    return _env().get_template("answer.jinja").render(
        questions=questions,
        enable_web_search=enable_web_search,
    )
