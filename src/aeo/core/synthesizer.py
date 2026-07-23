"""AI synthesis pass (PRD FR-21 sheet 8, June "AI Insights & Quotes").

After the deterministic analysis, one LLM call reads a compact summary of the run
plus a few answer excerpts and writes qualitative per-question interpretations,
narrative findings, and representative pull-quotes. This is what turns the report
from templated bullet-stats into analysis.
"""

from __future__ import annotations

import json
import re
from typing import Any

from aeo.analysis.models import AnalysisResult
from aeo.logging import get_logger
from aeo.providers.base import ChatMessage, LLMProvider
from aeo.schemas.company import CompanyProfile
from aeo.schemas.run import ModelResponseRecord

log = get_logger(__name__)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["question_interpretations", "findings", "quotes", "recommendations"],
    "additionalProperties": False,
    "properties": {
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "question_interpretations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["index", "interpretation"],
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "interpretation": {"type": "string"},
                },
            },
        },
        "findings": {"type": "array", "items": {"type": "string"}},
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["model", "quote"],
                "additionalProperties": False,
                "properties": {
                    "model": {"type": "string"},
                    "quote": {"type": "string"},
                },
            },
        },
    },
}

_SYSTEM = ChatMessage(
    role="system",
    content="You are a brand-visibility analyst. Output only valid JSON per the schema.",
)


def _summary(company: CompanyProfile, analysis: AnalysisResult) -> str:
    lines = [f"Brand: {company.name}", f"Category: {company.category or 'n/a'}", ""]
    lines.append("Per-question mention stats:")
    for q in analysis.questions:
        lines.append(
            f"  Q{q.index}: \"{q.text}\" — {q.total_mentions} mentions across "
            f"{q.models_mentioning}/{len(analysis.models)} models (peak: {q.peak_model or 'none'})"
        )
    prov = dict.fromkeys(("organic", "search_driven", "absent"), 0)
    for m in analysis.models:
        prov[m.provenance.value] = prov.get(m.provenance.value, 0) + 1
    lines.append(
        f"\nProvenance: {prov['organic']} organic, {prov['search_driven']} search-driven, "
        f"{prov['absent']} absent."
    )
    comp_totals: dict[str, int] = {}
    for m in analysis.models:
        for c, v in m.competitor_totals.items():
            comp_totals[c] = comp_totals.get(c, 0) + v
    top_comp = sorted(comp_totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    lines.append("Competitor share-of-voice (total mentions): "
                 + ", ".join(f"{c} {v}" for c, v in top_comp if v))
    top_domains = [
        f"{d.domain}({d.num_models}{'*' if d.brand_owned else ''})"
        for d in analysis.domain_frequency[:10]
    ]
    lines.append("Top cited domains (models citing, *=brand-owned): " + ", ".join(top_domains))
    zero = [q for q in analysis.questions if q.total_mentions == 0]
    if zero:
        lines.append(
            "Questions with ZERO brand mentions (biggest content gaps): "
            + "; ".join(f"Q{q.index} \"{q.text}\"" for q in zero)
        )
    brand_owned = sum(1 for m in analysis.models for c in m.citations if c.brand_owned)
    lines.append(f"Brand-owned domains cited by models: {brand_owned}.")
    return "\n".join(lines)


def _excerpts(responses: list[ModelResponseRecord], limit: int = 4) -> str:
    out: list[str] = []
    for r in responses[:limit]:
        if r.content:
            out.append(f"--- {r.model_id} (excerpt) ---\n{r.content[:900]}")
    return "\n\n".join(out)


async def synthesize(
    provider: LLMProvider,
    model: str,
    company: CompanyProfile,
    analysis: AnalysisResult,
    responses: list[ModelResponseRecord],
    *,
    max_tokens: int = 3000,
) -> dict[str, Any] | None:
    """Return {question_interpretations, findings, quotes} or None on failure."""
    prompt = (
        f"Analyze this AI brand-visibility run for {company.name} and write insight.\n\n"
        f"{_summary(company, analysis)}\n\n"
        f"Representative answer excerpts:\n{_excerpts(responses)}\n\n"
        "Produce JSON with:\n"
        "- question_interpretations: for each question index, a one-sentence qualitative "
        "read of how the brand fared and why (positioning, framing, gaps).\n"
        "- findings: 5-8 sharp, specific narrative findings a marketer would act on.\n"
        "- quotes: 3-6 short verbatim pull-quotes from the excerpts that best illustrate "
        "how models describe the brand (attribute each to its model).\n"
        "- recommendations: 5-8 concrete, tactical actions THIS company should take to "
        f"improve how AI models represent {company.name}, grounded in the specific gaps "
        "above. Be specific, not generic. Favor answer-engine-optimization moves such as: "
        "publishing content that directly answers the zero-mention questions (e.g. a blog "
        "post or FAQ titled as that exact buyer question), earning citations on the "
        "authoritative third-party sites the models already cite, publishing crawlable, "
        "indexable content on the brand's own domain, and claiming distinctive positioning "
        "wedges competitors ignore. Each recommendation is one imperative sentence and "
        "names the concrete artifact to create or place."
    )
    try:
        result = await provider.chat(
            model,
            [_SYSTEM, ChatMessage(role="user", content=prompt)],
            max_tokens=max_tokens,
            temperature=0.4,
            response_schema=_SCHEMA,
        )
        return _parse(result.content)
    except Exception as exc:  # synthesis is best-effort; never fail the run
        log.warning("synthesis_failed", error=str(exc))
        return None


def apply_synthesis(analysis: AnalysisResult, synth: dict[str, Any]) -> None:
    """Merge AI-written interpretations, findings, and quotes into the analysis."""
    interp = {
        int(i["index"]): i["interpretation"]
        for i in synth.get("question_interpretations", [])
    }
    for q in analysis.questions:
        if q.index in interp and interp[q.index].strip():
            q.interpretation = interp[q.index].strip()
    findings = [f.strip() for f in synth.get("findings", []) if f.strip()]
    if findings:
        # Keep the deterministic headline stats, then the AI narrative.
        analysis.insights = analysis.insights[:2] + findings
    quotes = [
        {"model": q.get("model", ""), "quote": q.get("quote", "").strip()}
        for q in synth.get("quotes", [])
        if q.get("quote", "").strip()
    ]
    if quotes:
        analysis.quotes = quotes
    recommendations = [r.strip() for r in synth.get("recommendations", []) if r.strip()]
    if recommendations:
        analysis.recommendations = recommendations


def _parse(content: str) -> dict[str, Any] | None:
    content = content.strip()
    try:
        parsed: dict[str, Any] = json.loads(content)
        return parsed
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                return dict(json.loads(m.group(0)))
            except json.JSONDecodeError:
                return None
    return None
