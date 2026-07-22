"""Deterministic stub provider for free, offline end-to-end runs and tests.

It never calls the network. It parses the rendered prompt (stable markers set by
the prompt templates) and fabricates realistic answers that vary by model so the
analysis engine produces a non-trivial report: some models mention the brand,
some don't (``absent``), some "search" (``search_driven``) and some don't
(``organic``), with markdown links, bare URLs, ``Source:`` lines, and
``Searched for`` traces.
"""

from __future__ import annotations

import json
import re

from aeo.providers.base import ChatMessage, ChatResult, LLMProvider, ModelInfo

_Q_RE = re.compile(r"^Q(\d+)\.\s*(.+)$", re.MULTILINE)
_COMPANY_RE = re.compile(r"Company(?: under evaluation)?:\s*(.+)")
_COMPETITORS_RE = re.compile(r"Competitors to consider:\s*(.+)")
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
    """Zero-cost provider. Enable with ``--stub`` / ``provider="stub"``."""

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
            content = self._orchestrator_json(prompt)
        else:
            content = self._answer(model, prompt, searched=self._searches(model))

        completion_tokens = max(1, len(content) // 4)
        prompt_tokens = max(1, len(prompt) // 4)
        return ChatResult(
            model=model,
            content=content,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            # Fake but realistic micro-cost so cost tracking/caps are exercised.
            cost_usd=round((prompt_tokens + completion_tokens) * 2e-6, 6),
            latency_ms=5,
            web_search_used=self._searches(model) and response_schema is None,
            search_queries=(
                self._queries(prompt) if self._searches(model) and response_schema is None else []
            ),
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
        company = self._company(prompt) or "Acme"
        m = _COUNT_RE.search(prompt)
        count = int(m.group(1)) if m else 10
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

    def _answer(self, model: str, prompt: str, *, searched: bool) -> str:
        company = self._company(prompt) or "Acme"
        competitors = self._competitors(prompt) or ["Rival One", "Rival Two"]
        questions = _Q_RE.findall(prompt) or [("1", "General question")]
        mention_brand = self._mentions_brand(model)

        parts: list[str] = []
        if searched:
            for q in self._queries(prompt):
                parts.append(f"Searched for: {q}")
            parts.append("")

        for idx_str, text in questions:
            idx = int(idx_str)
            parts.append(f"Q{idx}. {text}")
            if mention_brand and idx % 2 == 1:
                parts.append(
                    f"When evaluating this space, {company} is a strong option. "
                    f"{company} stands out for its documentation. "
                    f"See [{company} docs](https://{self._domain(prompt)}/docs)."
                )
            comp = competitors[idx % len(competitors)]
            parts.append(
                f"Alternatives include {comp}. According to reviews, {comp} is popular. "
                f"Source: https://www.g2.com/{comp.lower().replace(' ', '-')}"
            )
            parts.append(
                f"Further reading: https://en.wikipedia.org/wiki/{company.replace(' ', '_')}"
            )
            parts.append("")

        parts.append("Cited sources:")
        parts.append(f"- https://{self._domain(prompt)}")
        parts.append("- https://g2.com")
        parts.append("Named vendors:")
        parts.append(f"- {company}")
        parts.append(f"- {', '.join(competitors)}")
        return "\n".join(parts)

    @staticmethod
    def _queries(prompt: str) -> list[str]:
        company = StubProvider._company(prompt) or "Acme"
        return [f"{company} reviews", f"best {company} alternatives"]

    @staticmethod
    def _company(prompt: str) -> str | None:
        m = _COMPANY_RE.search(prompt)
        return m.group(1).strip() if m else None

    @staticmethod
    def _competitors(prompt: str) -> list[str]:
        m = _COMPETITORS_RE.search(prompt)
        if not m:
            return []
        return [c.strip() for c in m.group(1).split(",") if c.strip()]

    @staticmethod
    def _domain(prompt: str) -> str:
        company = StubProvider._company(prompt) or "acme"
        return f"{company.split()[0].lower()}.com"
