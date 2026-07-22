"""Search-query trace parsing (PRD FR-17).

Combines queries the provider reported with any ``Searched for ...`` traces found
in the answer text.
"""

from __future__ import annotations

import re

_TRACE_RE = re.compile(
    r"(?:searched|searching|search)\s+(?:for|the web for|google for)?[:\s]+"
    r"[\"“']?(.+?)[\"”']?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_query_traces(content: str) -> list[str]:
    """Extract queries from 'Searched for: ...' style lines in the text."""
    queries: list[str] = []
    for m in _TRACE_RE.finditer(content):
        q = m.group(1).strip().strip("\"'“”")
        if q and len(q) <= 200:
            queries.append(q)
    return queries


def merge_queries(reported: list[str], content: str) -> list[str]:
    """Union of provider-reported queries and text-parsed traces (deduped)."""
    out: list[str] = []
    seen: set[str] = set()
    for q in [*reported, *parse_query_traces(content)]:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(q)
    return out
