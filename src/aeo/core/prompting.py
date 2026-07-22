"""Jinja rendering for orchestrator and answer prompts."""

from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aeo.constants import PACKAGE_ROOT
from aeo.schemas.company import CompanyProfile
from aeo.schemas.question import Question

_PROMPTS_DIR = PACKAGE_ROOT / "core" / "prompts"

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
) -> str:
    return _env().get_template("orchestrator.jinja").render(
        company=company,
        question_count=question_count,
        categories=categories or DEFAULT_CATEGORIES,
    )


def render_answer(
    company: CompanyProfile,
    competitors: list[str],
    questions: list[Question],
) -> str:
    return _env().get_template("answer.jinja").render(
        company=company,
        competitors=competitors,
        questions=questions,
    )
