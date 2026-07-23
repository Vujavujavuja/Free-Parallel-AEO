"""Synthesis merge must never surface placeholder/stub values a model emits
when it runs low on tokens (the '1. placeholder' recommendation bug)."""

from __future__ import annotations

from aeo.analysis.models import AnalysisResult, QuestionAggregate
from aeo.core import synthesizer


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
