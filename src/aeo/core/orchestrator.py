"""Orchestrator: turn a company profile into a structured question set using a
JSON-schema-constrained model call (PRD FR-4..FR-6, Appendix B, D).

The orchestrator is resilient by design: even a sparse profile (just a name, or a
name + website) yields a full question set. It infers blank profile fields from
whatever it is given, and if the model returns too few questions it retries once
and then tops up from a neutral generic template so a run never dies here."""

from __future__ import annotations

import json
import re
from typing import Any

from aeo.core.prompting import DEFAULT_CATEGORIES, render_orchestrator
from aeo.exceptions import OrchestratorError
from aeo.logging import get_logger
from aeo.providers.base import ChatMessage, LLMProvider
from aeo.schemas.company import CompanyProfile, SourceDocument
from aeo.schemas.question import InferredProfile, Question, QuestionSet

log = get_logger(__name__)

_ORCHESTRATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions", "competitors", "brand_aliases", "inferred"],
    "additionalProperties": False,
    "properties": {
        "competitors": {"type": "array", "items": {"type": "string"}},
        "brand_aliases": {"type": "array", "items": {"type": "string"}},
        "inferred": {
            "type": "object",
            "additionalProperties": False,
            "required": ["category", "description", "products", "regions"],
            "properties": {
                "category": {"type": "string"},
                "description": {"type": "string"},
                "products": {"type": "array", "items": {"type": "string"}},
                "regions": {"type": "array", "items": {"type": "string"}},
            },
        },
        "questions": {
            "type": "array",
            "minItems": 1,
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
    max_tokens: int | None = None,
    categories: list[str] | None = None,
    documents: list[SourceDocument] | None = None,
    existing_questions: list[str] | None = None,
    language: str = "English",
) -> QuestionSet:
    """Call the orchestrator model and parse its structured question set. Always
    returns at least ``question_count`` questions (falling back to a neutral
    generic set if the model under-delivers)."""
    cats = categories or DEFAULT_CATEGORIES
    existing = existing_questions or []
    # Generous token budget that also scales with the count so a large set can't
    # be truncated mid-JSON (each question carries text + intent + source types).
    budget = max_tokens or max(8000, question_count * 400 + 4000)

    qset = await _generate_once(
        provider, company, model=model, question_count=question_count,
        max_tokens=budget, categories=cats,
        documents=documents, existing_questions=existing, language=language,
    )

    # If the model under-delivered, retry once for just the shortfall, using the
    # questions we already have as "existing" so it doesn't duplicate them.
    if len(qset.questions) < question_count:
        shortfall = question_count - len(qset.questions)
        have = existing + [q.text for q in qset.questions]
        try:
            more = await _generate_once(
                provider, company, model=model, question_count=shortfall,
                max_tokens=budget, categories=cats,
                documents=documents, existing_questions=have, language=language,
            )
            qset.questions.extend(more.questions)
            qset.competitors = _dedup(qset.competitors + more.competitors)
            qset.brand_aliases = _dedup(qset.brand_aliases + more.brand_aliases)
            qset.inferred = qset.inferred or more.inferred
        except OrchestratorError as exc:
            log.warning("orchestrator_retry_failed", error=str(exc))

    # Last-resort top-up so the run always proceeds with a full set.
    if len(qset.questions) < question_count:
        missing = question_count - len(qset.questions)
        log.warning("orchestrator_fallback", requested=question_count, got=len(qset.questions))
        qset.questions.extend(
            _fallback_questions(company, missing, cats, len(qset.questions))
        )

    # Trim to the requested count and normalize indices to 1..N.
    qset.questions = [
        Question(
            index=i + 1,
            category=q.category,
            text=q.text,
            intent=q.intent,
            expected_source_types=q.expected_source_types,
        )
        for i, q in enumerate(qset.questions[:question_count])
    ]
    return qset


async def _generate_once(
    provider: LLMProvider,
    company: CompanyProfile,
    *,
    model: str,
    question_count: int,
    max_tokens: int,
    categories: list[str],
    documents: list[SourceDocument] | None,
    existing_questions: list[str],
    language: str = "English",
) -> QuestionSet:
    """One orchestrator call → parsed, validated question set (may be short)."""
    prompt = render_orchestrator(
        company, question_count, categories,
        documents=documents, existing_questions=existing_questions,
        language=language,
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
        return QuestionSet.model_validate(data)
    except Exception as exc:
        raise OrchestratorError(f"Orchestrator returned an invalid question set: {exc}") from exc


# Neutral, brand-free buyer questions keyed off the company's category. Used only
# to fill a shortfall so a run never fails for lack of questions.
_FALLBACK_TEMPLATES = [
    "What are the best {cat} tools available right now?",
    "How should a team evaluate and choose a {cat} solution?",
    "What features matter most when comparing {cat} platforms?",
    "Which {cat} vendors are most commonly recommended, and why?",
    "What are the main alternatives in the {cat} space?",
    "How do {cat} products typically handle pricing and plans?",
    "What integrations should I expect from a modern {cat} tool?",
    "What are common pitfalls when adopting {cat} software?",
    "How do teams measure the ROI of a {cat} solution?",
    "What security and compliance factors matter for {cat} software?",
    "What do reviews and users say about the leading {cat} tools?",
    "How does a {cat} product typically scale for larger organizations?",
]


def _fallback_questions(
    company: CompanyProfile, count: int, categories: list[str], start: int
) -> list[Question]:
    cat = (company.category or (categories[0] if categories else "") or "software").strip()
    cat = re.sub(r"\bsoftware\b|\btools?\b|\bplatforms?\b", "", cat, flags=re.I).strip() or cat
    out: list[Question] = []
    for i in range(count):
        text = _FALLBACK_TEMPLATES[(start + i) % len(_FALLBACK_TEMPLATES)].format(cat=cat)
        out.append(
            Question(
                index=start + i + 1,
                category="general",
                text=text,
                intent="generic buyer research (auto-filled)",
            )
        )
    return out


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


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


def enrich_company(company: CompanyProfile, inferred: InferredProfile | None) -> list[str]:
    """Fill blank profile fields from the orchestrator's inference. Only fills
    what the user left empty — never overwrites provided values. Returns the
    names of the fields that were filled (for logging)."""
    if inferred is None:
        return []
    filled: list[str] = []
    if not company.category and inferred.category.strip():
        company.category = inferred.category.strip()
        filled.append("category")
    if not company.description and inferred.description.strip():
        company.description = inferred.description.strip()
        filled.append("description")
    if not company.products and inferred.products:
        company.products = _dedup(inferred.products)
        filled.append("products")
    if not company.regions and inferred.regions:
        company.regions = _dedup(inferred.regions)
        filled.append("regions")
    return filled
