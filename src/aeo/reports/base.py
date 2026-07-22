"""Shared report helpers, incl. CSV/formula-injection sanitization (PRD §16)."""

from __future__ import annotations

from aeo.analysis import AnalysisResult
from aeo.schemas.run import RunRecord

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: object) -> object:
    """Neutralize spreadsheet-formula injection in text cells by prefixing a
    leading apostrophe (Excel renders it as text, hiding the quote)."""
    if isinstance(value, str) and value and value.startswith(_DANGEROUS_PREFIXES):
        return "'" + value
    return value


def get_analysis(record: RunRecord) -> AnalysisResult:
    """Reconstruct the typed analysis from the stored record (or empty)."""
    if record.analysis:
        return AnalysisResult.model_validate(record.analysis)
    return AnalysisResult()
