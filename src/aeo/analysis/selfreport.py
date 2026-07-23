"""Parse the models' self-reported sources (PRD FR-16, June methodology).

The neutral answer prompt asks each model to fill a Results Table
(``| # | Question | Websites Cited | Websites Mentioned |``) and to note cited /
mentioned sources per answer. This extracts both into per-question lists of the
sites the model *says* it cited vs merely *named*.
"""

from __future__ import annotations

import re

_TABLE_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|[^|]*\|([^|]*)\|([^|]*)\|", re.MULTILINE)
_CITED_RE = re.compile(r"(?:websites?\s+)?cited\s*(?:sources)?\s*[:\-]\s*(.+)", re.IGNORECASE)
_NAMED_RE = re.compile(
    r"(?:websites?\s+)?(?:mentioned|named|named vendors)\s*[:\-]\s*(.+)", re.IGNORECASE
)
_JUNK = {"", "-", "\u2014", "\u2013", "none", "n/a", "na", "example url"}
_SITE_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", re.IGNORECASE)


def _norm_site(item: str) -> str:
    """Reduce a URL/domain to a bare host; leave plain names untouched."""
    m = _SITE_RE.fullmatch(item.strip().rstrip("/"))
    return m.group(1).lower() if m else item


def _split_items(cell: str) -> list[str]:
    parts = re.split(r"[,;]|\band\b|\|", cell)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        item = p.strip().strip("`*[]")
        key = item.lower()
        if key and key not in _JUNK and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _merge(*lists: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for item in lst:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def parse_self_report(content: str, segments: dict[int, str]) -> dict[int, dict[str, list[str]]]:
    """Return ``{question_index: {"cited": [...], "named": [...]}}``."""
    table: dict[int, dict[str, list[str]]] = {}
    for m in _TABLE_ROW_RE.finditer(content):
        idx = int(m.group(1))
        table[idx] = {"cited": _split_items(m.group(2)), "named": _split_items(m.group(3))}

    per_q: dict[int, dict[str, list[str]]] = {}
    for idx, text in segments.items():
        if idx == 0:
            continue
        cited: list[str] = []
        named: list[str] = []
        for line in text.splitlines():
            cm = _CITED_RE.search(line)
            nm = _NAMED_RE.search(line)
            if nm:
                named += _split_items(nm.group(1))
            elif cm:
                cited += _split_items(cm.group(1))
        if cited or named:
            per_q[idx] = {"cited": cited, "named": named}

    merged: dict[int, dict[str, list[str]]] = {}
    for idx in set(table) | set(per_q):
        cited = _merge(
            table.get(idx, {}).get("cited", []), per_q.get(idx, {}).get("cited", [])
        )
        merged[idx] = {
            "cited": _merge([_norm_site(c) for c in cited]),  # dedupe by bare host
            "named": _merge(
                table.get(idx, {}).get("named", []), per_q.get(idx, {}).get("named", [])
            ),
        }
    return merged
