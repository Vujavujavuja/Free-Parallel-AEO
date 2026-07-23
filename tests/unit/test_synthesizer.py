"""Synthesis merge must never surface placeholder/stub values a model emits
when it runs low on tokens (the '1. placeholder' recommendation bug)."""

from __future__ import annotations

from aeo.analysis.models import AnalysisResult, DomainStat, ModelAnalysis, QuestionAggregate
from aeo.core import synthesizer
from aeo.schemas.company import CompanyProfile


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        questions=[QuestionAggregate(index=1, text="Q1"), QuestionAggregate(index=2, text="Q2")],
        insights=["stat one.", "stat two."],
    )


def test_placeholder_recommendations_are_dropped() -> None:
    a = _analysis()
    synthesizer.apply_synthesis(a, {"recommendations": ["placeholder"]})
    assert a.recommendations == []  # junk filtered -> section won't render


def test_real_recommendations_survive_junk_mixed_in() -> None:
    a = _analysis()
    synthesizer.apply_synthesis(a, {
        "recommendations": [
            "placeholder",
            "n/a",
            "Publish a FAQ page answering the zero-mention buyer questions verbatim.",
            "tbd",
        ],
    })
    assert a.recommendations == [
        "Publish a FAQ page answering the zero-mention buyer questions verbatim.",
    ]


def test_junk_findings_and_quotes_filtered() -> None:
    a = _analysis()
    real_finding = "The brand is invisible on pricing questions across all models."
    synthesizer.apply_synthesis(a, {
        "findings": ["placeholder", real_finding],
        "quotes": [
            {"model": "m", "quote": "placeholder"},
            {"model": "n", "quote": "Acme is the strongest option here."},
        ],
    })
    # insights = deterministic first two + cleaned findings
    assert a.insights[2:] == [real_finding]
    assert a.quotes == [{"model": "n", "quote": "Acme is the strongest option here."}]


def test_ensure_recommendations_fallback_when_ai_empty() -> None:
    """If the AI pass returns no recommendations, a deterministic brand-specific
    set is generated so the 'How to improve' section is never empty."""
    company = CompanyProfile(name="Acme", website="https://acme.co")
    a = AnalysisResult(
        questions=[
            QuestionAggregate(index=1, text="How do teams pick a vendor?", total_mentions=0),
            QuestionAggregate(index=2, text="What does pricing look like?", total_mentions=0),
        ],
        models=[ModelAnalysis(model_id="m", competitor_totals={"Rival": 9})],
        domain_frequency=[DomainStat(domain="g2.com", num_models=3, models=["m"])],
    )
    assert a.recommendations == []
    synthesizer.ensure_recommendations(company, a)
    assert len(a.recommendations) >= 3
    joined = " ".join(a.recommendations)
    assert "Rival" in joined            # competitor wedge
    assert "g2.com" in joined           # third-party citation target
    assert "acme.co" in joined          # own-domain content


def test_ensure_recommendations_keeps_ai_ones() -> None:
    company = CompanyProfile(name="Acme")
    a = AnalysisResult(recommendations=["Do the AI-written thing specifically."])
    synthesizer.ensure_recommendations(company, a)
    assert a.recommendations == ["Do the AI-written thing specifically."]
