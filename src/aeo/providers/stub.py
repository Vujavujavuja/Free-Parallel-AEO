"""Deterministic stub provider for free, offline end-to-end runs and tests.

It never calls the network. For the orchestrator call it parses the company name
from the (company-bearing) orchestrator prompt. For answer calls it uses context
supplied via :meth:`configure` — because the neutral answer prompt intentionally
contains no brand or competitor names. It fabricates realistic answers that vary
by model so the analysis engine produces a non-trivial report: some models
mention the brand, some don't (``absent``), some "search" (``search_driven``).
"""

from __future__ import annotations

import json
import re

from aeo.providers.base import ChatMessage, ChatResult, LLMProvider, ModelInfo

_Q_RE = re.compile(r"^##\s*Q(\d+)\.\s*(.+)$", re.MULTILINE)
_COMPANY_RE = re.compile(r"Company:\s*(.+)")
_COUNT_RE = re.compile(r"exactly\s+(\d+)\s+", re.IGNORECASE)

_STUB_PANEL = [
    "openai/gpt-stub",
    "anthropic/claude-stub",
    "google/gemini-stub",
    "meta/llama-stub",
    "mistral/mistral-stub",
]


def _hash(text: str) -> int:
    return sum(ord(c) for c in text)


class StubProvider(LLMProvider):
    """Zero-cost provider. Enable with ``provider="stub"``."""

    def __init__(self) -> None:
        self._brand = "Acme"
        self._brand_terms: list[str] = ["Acme"]
        self._competitors: list[str] = ["Rival One", "Rival Two"]
        self._domain = "acme.com"

    def configure(self, brand_terms: list[str], competitors: list[str]) -> None:
        """Supply the brand/competitor context for answer fabrication."""
        if brand_terms:
            self._brand = brand_terms[0]
            self._brand_terms = brand_terms
            self._domain = next(
                (t.lower() for t in brand_terms if "." in t),
                f"{self._brand.split()[0].lower()}.com",
            )
        if competitors:
            self._competitors = competitors

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
        prompt = "\n".join(m.content for m in messages)
        if response_schema is not None:
            props = response_schema.get("properties", {})
            content = (
                self._synthesis_json(prompt)
                if isinstance(props, dict) and "findings" in props
                else self._orchestrator_json(prompt)
            )
            searched = False
        else:
            searched = self._searches(model)
            content = self._answer(model, prompt, searched=searched)

        completion_tokens = max(1, len(content) // 4)
        prompt_tokens = max(1, len(prompt) // 4)
        return ChatResult(
            model=model,
            content=content,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round((prompt_tokens + completion_tokens) * 2e-6, 6),
            latency_ms=5,
            web_search_used=searched,
            search_queries=self._queries() if searched else [],
        )

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=m, name=m, context_length=128000) for m in _STUB_PANEL]

    # --- helpers ---

    @staticmethod
    def _searches(model: str) -> bool:
        return _hash(model) % 2 == 0

    @staticmethod
    def _mentions_brand(model: str) -> bool:
        # ~1 in 3 models don't mention the brand at all -> "absent" provenance.
        return _hash(model) % 3 != 0

    def _orchestrator_json(self, prompt: str) -> str:
        m = _COMPANY_RE.search(prompt)
        company = m.group(1).strip() if m else "Acme"
        count_m = _COUNT_RE.search(prompt)
        count = int(count_m.group(1)) if count_m else 10
        categories = [
            "need", "approaches", "differentiation", "evaluation_criteria",
            "pricing", "results_roi", "regulated_fit", "onboarding",
            "risks", "testimonials",
        ]
        questions = []
        for i in range(count):
            topic = categories[i % len(categories)].replace("_", " ")
            questions.append(
                {
                    "index": i + 1,
                    "category": categories[i % len(categories)],
                    "text": f"What should buyers know about {topic} when evaluating {company}?",
                    "intent": "buyer research",
                    "expected_source_types": ["vendor docs", "analyst", "review site"],
                }
            )
        return json.dumps(
            {
                "questions": questions,
                "competitors": ["Rival One", "Rival Two", "Rival Three"],
                "brand_aliases": [company, company.split()[0]],
            }
        )

    def _synthesis_json(self, prompt: str) -> str:
        brand = self._brand
        idxs = sorted({int(m) for m in re.findall(r"Q(\d+):", prompt)}) or list(range(1, 11))
        qi = [
            {
                "index": i,
                "interpretation": (
                    f"{brand} shows moderate visibility on question {i}; framing stays "
                    f"category-first with {brand} positioned on differentiation."
                ),
            }
            for i in idxs
        ]
        findings = [
            f"{brand} is surfaced by most models, primarily organically.",
            f"Competitors cluster around a few well-known names; {brand} holds share on "
            "differentiation questions.",
            "Brand-owned domains are cited alongside third-party review sites.",
            "Pricing and onboarding questions show the thinnest brand coverage.",
            "Search-driven models lean on analyst and review sources.",
        ]
        quotes = [
            {"model": m, "quote": f"{brand} is a strong option for teams evaluating this category."}
            for m in _STUB_PANEL[:3]
        ]
        return json.dumps(
            {"question_interpretations": qi, "findings": findings, "quotes": quotes}
        )

    def _answer(self, model: str, prompt: str, *, searched: bool) -> str:
        brand = self._brand
        competitors = self._competitors
        questions = _Q_RE.findall(prompt) or [("1", "General question")]
        mention_brand = self._mentions_brand(model)

        parts: list[str] = ["## Results Table",
                            "| # | Question Summary | Websites Cited | Websites Mentioned |",
                            "|---|---|---|---|"]
        for idx_str, text in questions:
            cited = f"{self._domain}, g2.com" if mention_brand else "g2.com, wikipedia.org"
            named = f"{brand}, {competitors[0]}" if mention_brand else competitors[0]
            parts.append(f"| {idx_str} | {text[:40]} | {cited} | {named} |")
        parts.append("")

        for idx_str, text in questions:
            idx = int(idx_str)
            parts.append(f"## Q{idx}. {text}")
            if mention_brand and idx % 2 == 1:
                parts.append(
                    f"When evaluating this space, {brand} is a strong option. "
                    f"{brand} stands out for its documentation. "
                    f"See [{brand} docs](https://{self._domain}/docs)."
                )
            comp = competitors[idx % len(competitors)]
            parts.append(
                f"Alternatives include {comp}. According to reviews, {comp} is popular. "
                f"Source: https://www.g2.com/{comp.lower().replace(' ', '-')}"
            )
            cited = f"https://{self._domain}, https://g2.com" if mention_brand else "https://g2.com"
            named = f"{brand}, {comp}" if mention_brand else comp
            parts.append(f"Cited: {cited}")
            parts.append(f"Mentioned: {named}")
            parts.append("")

        if searched:
            parts.append("## Searches performed")
            parts.extend(self._queries())
        return "\n".join(parts)

    def _queries(self) -> list[str]:
        return [f"{self._brand} reviews", f"best {self._brand} alternatives"]
