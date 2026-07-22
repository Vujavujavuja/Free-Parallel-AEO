"""Deterministic analysis engine: segmentation, mentions, citations, queries,
provenance, and cross-model aggregates (PRD FR-14..FR-20)."""

from __future__ import annotations

from aeo.analysis.metrics import analyze
from aeo.analysis.models import (
    AnalysisResult,
    CitationRecord,
    DomainStat,
    ModelAnalysis,
    QuestionAggregate,
)

__all__ = [
    "AnalysisResult",
    "CitationRecord",
    "DomainStat",
    "ModelAnalysis",
    "QuestionAggregate",
    "analyze",
]
