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


_SEARCHES_SECTION_RE = re.compile(
    r"##\s*Searches?\s+performed\s*\n(.+?)(?:\n##\s|\Z)", re.IGNORECASE | re.DOTALL
)


def parse_searches_section(content: str) -> list[str]:
    """Extract queries listed under a '## Searches performed' heading."""
    m = _SEARCHES_SECTION_RE.search(content)
    if not m:
        return []
    queries: list[str] = []
    for raw in m.group(1).splitlines():
        line = raw.strip().lstrip("-*0123456789. ").strip("\"'`").strip()
        if line and not line.startswith("[") and len(line) <= 200:
            queries.append(line)
    return queries


def merge_queries(reported: list[str], content: str) -> list[str]:
    """Union of provider-reported queries, the 'Searches performed' section, and
    inline 'Searched for' traces (deduped)."""
    out: list[str] = []
    seen: set[str] = set()
    candidates = [*reported, *parse_searches_section(content), *parse_query_traces(content)]
    for q in candidates:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(q)
    return out
