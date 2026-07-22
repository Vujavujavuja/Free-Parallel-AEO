"""Aggregate per-model analysis into the full :class:`AnalysisResult`
(PRD FR-19..FR-20)."""

from __future__ import annotations

import re

from aeo.analysis.citations import extract_citations
from aeo.analysis.mentions import count_any, in_vendor_table
from aeo.analysis.models import (
    AnalysisResult,
    DomainStat,
    ModelAnalysis,
    QuestionAggregate,
)
from aeo.analysis.queries import merge_queries
from aeo.analysis.segmenter import segment
from aeo.constants import Provenance
from aeo.schemas.company import CompanyProfile
from aeo.schemas.question import Question
from aeo.schemas.run import ModelResponseRecord, RunRecord

_SENTENCE_RE = re.compile(r"[^.!?\n]*[.!?]")


def _provenance(brand_mentions: int, num_searches: int) -> Provenance:
    if brand_mentions > 0 and num_searches == 0:
        return Provenance.ORGANIC
    if brand_mentions > 0 and num_searches > 0:
        return Provenance.SEARCH_DRIVEN
    return Provenance.ABSENT


def _segments_for(model: str, recs: list[ModelResponseRecord]) -> dict[int, str]:
    segments: dict[int, str] = {}
    for r in recs:
        if r.question_index is None:
            for idx, text in segment(r.content).items():
                segments[idx] = f"{segments.get(idx, '')}\n{text}".strip()
        else:
            segments[r.question_index] = (
                f"{segments.get(r.question_index, '')}\n{r.content}".strip()
            )
    return segments


def _analyze_model(
    model: str,
    recs: list[ModelResponseRecord],
    company: CompanyProfile,
    questions: list[Question],
    competitors: list[str],
) -> ModelAnalysis:
    combined = "\n".join(r.content for r in recs)
    segments = _segments_for(model, recs)
    brand_terms = company.brand_terms
    product_terms = company.products

    per_question_brand: dict[int, int] = {}
    for q in questions:
        seg = segments.get(q.index, "")
        per_question_brand[q.index] = count_any(seg, brand_terms) if seg else 0

    brand_mentions = sum(per_question_brand.values())
    # Also count mentions that landed in the preamble bucket (index 0).
    if 0 in segments:
        brand_mentions += count_any(segments[0], brand_terms)

    reported_queries: list[str] = []
    web_search_used = False
    for r in recs:
        reported_queries.extend(r.search_queries)
        web_search_used = web_search_used or r.web_search_used
    search_queries = merge_queries(reported_queries, combined)
    num_searches = len(search_queries)

    citations = extract_citations(segments, company.domain)
    competitor_totals = {c: count_any(combined, [c]) for c in competitors}
    errors = [r.error for r in recs if r.error]

    return ModelAnalysis(
        model_id=model,
        provider=model.split("/")[0] if "/" in model else "",
        web_search_used=web_search_used or num_searches > 0,
        num_searches=num_searches,
        search_queries=search_queries,
        brand_mentions=brand_mentions,
        subbrand_mentions=count_any(combined, product_terms) if product_terms else 0,
        in_vendor_table=in_vendor_table(combined, brand_terms),
        questions_mentioning=sum(1 for v in per_question_brand.values() if v > 0),
        per_question_brand=per_question_brand,
        competitor_totals={k: v for k, v in competitor_totals.items() if v >= 0},
        citations=citations,
        unique_domains=sorted({c.domain for c in citations}),
        answer_length=len(combined),
        provenance=_provenance(brand_mentions, num_searches),
        error="; ".join(errors) if errors else None,
    )


def analyze(record: RunRecord) -> AnalysisResult:
    """Produce the full deterministic analysis for a completed fan-out."""
    company = record.company
    questions = record.questions
    competitors = record.competitors
    models = record.options.target_models
    q_indices = [q.index for q in questions]

    by_model: dict[str, list[ModelResponseRecord]] = {m: [] for m in models}
    for r in record.responses:
        by_model.setdefault(r.model_id, []).append(r)

    model_analyses = [
        _analyze_model(m, by_model.get(m, []), company, questions, competitors)
        for m in models
    ]

    heatmap = {ma.model_id: dict(ma.per_question_brand) for ma in model_analyses}
    competitor_sov = {ma.model_id: dict(ma.competitor_totals) for ma in model_analyses}

    question_aggs = _question_aggregates(questions, model_analyses, len(models))
    domain_freq = _domain_frequency(model_analyses)
    insights = _insights(company.name, model_analyses, competitors, domain_freq)
    quotes = _quotes(company.brand_terms, model_analyses, by_model)

    return AnalysisResult(
        models=model_analyses,
        question_indices=q_indices,
        questions=question_aggs,
        heatmap=heatmap,
        competitors=competitors,
        competitor_sov=competitor_sov,
        domain_frequency=domain_freq,
        insights=insights,
        quotes=quotes,
    )


def _question_aggregates(
    questions: list[Question], analyses: list[ModelAnalysis], num_models: int
) -> list[QuestionAggregate]:
    aggs: list[QuestionAggregate] = []
    for q in questions:
        counts = {ma.model_id: ma.per_question_brand.get(q.index, 0) for ma in analyses}
        total = sum(counts.values())
        mentioning = sum(1 for v in counts.values() if v > 0)
        peak = max(counts.items(), key=lambda kv: kv[1], default=("", 0))
        avg = round(total / num_models, 2) if num_models else 0.0
        if mentioning == 0:
            interp = "No model mentioned the brand for this question."
        elif mentioning == num_models:
            interp = "Every model mentioned the brand — strong coverage."
        else:
            interp = f"{mentioning}/{num_models} models mentioned the brand."
        aggs.append(
            QuestionAggregate(
                index=q.index, text=q.text, total_mentions=total,
                models_mentioning=mentioning, avg_per_model=avg,
                peak_model=peak[0] if peak[1] > 0 else "",
                interpretation=interp,
            )
        )
    return aggs


def _domain_frequency(analyses: list[ModelAnalysis]) -> list[DomainStat]:
    by_domain: dict[str, set[str]] = {}
    brand_owned: dict[str, bool] = {}
    for ma in analyses:
        for c in ma.citations:
            by_domain.setdefault(c.domain, set()).add(ma.model_id)
            brand_owned[c.domain] = brand_owned.get(c.domain, False) or c.brand_owned
    stats = [
        DomainStat(
            domain=d, num_models=len(models), models=sorted(models),
            brand_owned=brand_owned.get(d, False),
        )
        for d, models in by_domain.items()
    ]
    stats.sort(key=lambda s: (s.num_models, s.domain), reverse=True)
    return stats


def _first_sentence_with(text: str, terms: list[str]) -> str | None:
    lowered = [t.lower() for t in terms]
    for sentence in _SENTENCE_RE.findall(text):
        s: str = str(sentence).strip()
        if any(t in s.lower() for t in lowered) and 20 <= len(s) <= 300:
            return s
    return None


def _insights(
    brand: str,
    analyses: list[ModelAnalysis],
    competitors: list[str],
    domains: list[DomainStat],
) -> list[str]:
    n = len(analyses)
    mentioning = [ma for ma in analyses if ma.brand_mentions > 0]
    organic = sum(1 for ma in analyses if ma.provenance == Provenance.ORGANIC)
    search_driven = sum(1 for ma in analyses if ma.provenance == Provenance.SEARCH_DRIVEN)
    absent = sum(1 for ma in analyses if ma.provenance == Provenance.ABSENT)

    insights = [
        f"{len(mentioning)}/{n} models mentioned {brand} at least once.",
        f"Provenance: {organic} organic, {search_driven} search-driven, {absent} absent.",
    ]

    comp_totals: dict[str, int] = dict.fromkeys(competitors, 0)
    for ma in analyses:
        for c, v in ma.competitor_totals.items():
            comp_totals[c] = comp_totals.get(c, 0) + v
    if comp_totals:
        top = max(comp_totals.items(), key=lambda kv: kv[1])
        if top[1] > 0:
            insights.append(f"Most-mentioned competitor across models: {top[0]} ({top[1]}).")
    if domains:
        top_domain = domains[0]
        insights.append(
            f"Most-cited domain: {top_domain.domain} (cited by {top_domain.num_models} models)."
        )
    brand_owned_cites = sum(
        1 for ma in analyses for c in ma.citations if c.brand_owned
    )
    insights.append(f"Brand-owned citations across all models: {brand_owned_cites}.")
    return insights


def _quotes(
    brand_terms: list[str],
    analyses: list[ModelAnalysis],
    by_model: dict[str, list[ModelResponseRecord]],
) -> list[dict[str, str]]:
    """Representative pull-quotes: one brand-mentioning sentence per model."""
    quotes: list[dict[str, str]] = []
    for ma in analyses:
        if ma.brand_mentions <= 0:
            continue
        text = "\n".join(r.content for r in by_model.get(ma.model_id, []))
        sentence = _first_sentence_with(text, brand_terms)
        if sentence:
            quotes.append({"model": ma.model_id, "quote": sentence})
        if len(quotes) >= 6:
            break
    return quotes
