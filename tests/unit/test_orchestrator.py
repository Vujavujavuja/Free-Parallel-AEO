"""Orchestrator resilience: never returns zero questions, and fills blank
profile fields from the model's inference without overwriting provided ones."""

from __future__ import annotations

import json

import pytest

from aeo.core import orchestrator
from aeo.providers.base import ChatMessage, ChatResult, LLMProvider, ModelInfo
from aeo.schemas.company import CompanyProfile
from aeo.schemas.question import InferredProfile


class _ScriptedProvider(LLMProvider):
    """Returns a queued JSON payload per chat call (drains, then repeats last)."""

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = [json.dumps(p) for p in payloads]
        self.calls = 0

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float = 0.3,
        enable_web_search: bool = False,
        response_schema: dict[str, object] | None = None,
    ) -> ChatResult:
        content = self._payloads[min(self.calls, len(self._payloads) - 1)]
        self.calls += 1
        return ChatResult(
            model=model, content=content, finish_reason="stop",
            prompt_tokens=1, completion_tokens=1, cost_usd=0.0, latency_ms=1,
        )

    async def list_models(self) -> list[ModelInfo]:  # pragma: no cover - unused
        return []


def _q(i: int) -> dict:
    return {
        "index": i, "category": "general", "text": f"Question {i}?",
        "intent": "x", "expected_source_types": [],
    }


@pytest.mark.asyncio
async def test_empty_questions_falls_back_to_full_set() -> None:
    """Model returns zero questions twice -> generic fallback guarantees the count."""
    empty = {"questions": [], "competitors": [], "brand_aliases": [], "inferred": {}}
    provider = _ScriptedProvider([empty])
    company = CompanyProfile(name="Acme", category="project management")

    qset = await orchestrator.generate_questions(
        provider, company, model="m", question_count=8
    )

    assert len(qset.questions) == 8
    assert [q.index for q in qset.questions] == list(range(1, 9))
    # Fallback questions are neutral and do not name the brand.
    assert all("Acme" not in q.text for q in qset.questions)


@pytest.mark.asyncio
async def test_shortfall_is_topped_up_by_retry_then_fallback() -> None:
    first = {
        "questions": [_q(1), _q(2)], "competitors": ["A"],
        "brand_aliases": ["Acme"], "inferred": {},
    }
    second = {
        "questions": [_q(3), _q(4), _q(5)], "competitors": ["B"],
        "brand_aliases": ["Acme Inc"], "inferred": {},
    }
    provider = _ScriptedProvider([first, second])
    company = CompanyProfile(name="Acme")

    qset = await orchestrator.generate_questions(
        provider, company, model="m", question_count=6
    )

    assert provider.calls == 2  # initial + one retry for the shortfall
    assert len(qset.questions) == 6
    assert "A" in qset.competitors and "B" in qset.competitors


def test_enrich_company_only_fills_blanks() -> None:
    company = CompanyProfile(name="Acme", category="analytics")  # category provided
    inferred = InferredProfile(
        category="synthetic data",  # must NOT overwrite "analytics"
        description="Acme builds data tools.",
        products=["Acme SDK"],
        regions=["North America"],
    )

    filled = orchestrator.enrich_company(company, inferred)

    assert company.category == "analytics"  # preserved
    assert company.description == "Acme builds data tools."
    assert company.products == ["Acme SDK"]
    assert company.regions == ["North America"]
    assert set(filled) == {"description", "products", "regions"}


def test_enrich_company_handles_none() -> None:
    company = CompanyProfile(name="Acme")
    assert orchestrator.enrich_company(company, None) == []


def test_generic_aliases_dropped_from_brand_terms() -> None:
    """A generic-phrase alias like 'Free Security' must not be a match term,
    else it counts the plain English phrase (the Q9 false-positive bug)."""
    company = CompanyProfile(
        name="TheFreeSecurity",
        aliases=["The Free Security", "Free Security", "TheFreeSec"],
    )
    terms = [t.lower() for t in company.brand_terms]
    assert "thefreesecurity" in terms          # distinctive primary name kept
    assert "thefreesec" in terms               # distinctive alias kept
    assert "free security" not in terms        # generic phrase dropped
    assert "the free security" not in terms    # generic phrase dropped


def test_distinctive_multiword_alias_kept() -> None:
    company = CompanyProfile(name="Acme", aliases=["Acme Security", "Acme Cloud"])
    terms = [t.lower() for t in company.brand_terms]
    assert "acme security" in terms  # has a non-generic word -> kept
    assert "acme cloud" in terms
