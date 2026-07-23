"""Regression tests for the neutral prompt, self-report parsing, and synthesis."""

from __future__ import annotations

from aeo.analysis.models import AnalysisResult, ModelAnalysis, QuestionAggregate
from aeo.analysis.selfreport import parse_self_report
from aeo.constants import Provenance
from aeo.core.prompting import render_answer
from aeo.core.synthesizer import apply_synthesis
from aeo.schemas.question import Question


def test_answer_prompt_is_neutral() -> None:
    qs = [Question(index=1, category="need", text="How do teams evaluate this category?")]
    prompt = render_answer(qs, enable_web_search=True).lower()
    # No brand/competitor leakage — only the question and neutral instructions.
    for leak in ("company under", "competitors to consider", "datacebo", "acme"):
        assert leak not in prompt
    assert "results table" in prompt
    assert "searches performed" in prompt


def test_self_report_table_and_lines() -> None:
    content = (
        "## Results Table\n"
        "| # | Question Summary | Websites Cited | Websites Mentioned |\n"
        "|---|---|---|---|\n"
        "| 1 | pricing | acme.com, g2.com | Acme, Gretel |\n"
        "## Q1. pricing?\n"
        "Cited: https://acme.com\n"
        "Mentioned: Acme, Tonic\n"
    )
    segments = {1: "Cited: https://acme.com\nMentioned: Acme, Tonic"}
    sr = parse_self_report(content, segments)
    assert "acme.com" in sr[1]["cited"]
    assert "g2.com" in sr[1]["cited"]
    assert "Tonic" in sr[1]["named"]


def test_apply_synthesis_merges() -> None:
    analysis = AnalysisResult(
        questions=[QuestionAggregate(index=1, text="q", interpretation="templated")],
        models=[ModelAnalysis(model_id="m", provenance=Provenance.ORGANIC)],
        insights=["stat one", "stat two"],
    )
    apply_synthesis(analysis, {
        "question_interpretations": [{"index": 1, "interpretation": "AI-written read"}],
        "findings": ["sharp finding"],
        "quotes": [{"model": "m", "quote": "great product"}],
    })
    assert analysis.questions[0].interpretation == "AI-written read"
    assert "sharp finding" in analysis.insights
    assert analysis.quotes[0]["quote"] == "great product"
