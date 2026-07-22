"""Split a model answer into per-question segments (PRD FR-14).

Handles headers like ``Q1.``, ``Q1:``, ``Q1)``, ``## Q1``, ``**Q1.**``, and
``Question 1``. Text before the first header (e.g. search traces / preamble) is
returned under index 0.
"""

from __future__ import annotations

import re

# Matches a question header at the start of a line, tolerating markdown wrappers.
_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*{1,2})?(?:Q|Question)\s*#?(\d+)(?:\*{1,2})?\s*[.):\-]?",
    re.IGNORECASE | re.MULTILINE,
)


def segment(content: str) -> dict[int, str]:
    """Return ``{question_index: segment_text}``; preamble is key 0.

    If no headers are found the whole answer is returned under key 0.
    """
    matches = list(_HEADER_RE.finditer(content))
    if not matches:
        return {0: content.strip()} if content.strip() else {}

    segments: dict[int, str] = {}
    preamble = content[: matches[0].start()].strip()
    if preamble:
        segments[0] = preamble

    for i, m in enumerate(matches):
        idx = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        # If the same index appears twice, concatenate rather than overwrite.
        if idx in segments:
            segments[idx] = f"{segments[idx]}\n{body}".strip()
        else:
            segments[idx] = body
    return segments
