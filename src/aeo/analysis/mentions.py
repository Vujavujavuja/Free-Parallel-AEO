"""Brand and competitor mention counting (PRD FR-15, FR-18).

Word-boundary, case-insensitive matching of a set of terms within a text.
"""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    # \b doesn't work well around non-word chars (e.g. "acme.com"), so we anchor
    # on non-alphanumeric boundaries instead.
    escaped = re.escape(term.strip())
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def count_term(text: str, term: str) -> int:
    if not term.strip():
        return 0
    return len(_term_pattern(term).findall(text))


def count_any(text: str, terms: list[str]) -> int:
    """Total occurrences across all terms (overlapping terms may double-count;
    callers pass a de-duplicated term list)."""
    return sum(count_term(text, t) for t in terms)


def mentions_present(text: str, terms: list[str]) -> bool:
    return any(_term_pattern(t).search(text) for t in terms if t.strip())


_TABLE_HINT_RE = re.compile(r"(recommended|vendor|comparison|top\s+\d+|shortlist)", re.IGNORECASE)


def in_vendor_table(content: str, terms: list[str]) -> bool:
    """Heuristic: does a brand term appear in a markdown table row or in a
    'recommended vendors / named vendors' style list?"""
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_table_row = line.count("|") >= 2
        is_vendor_list = _TABLE_HINT_RE.search(line) is not None
        if (is_table_row or is_vendor_list) and mentions_present(line, terms):
            return True
    return False
