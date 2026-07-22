"""Citation / domain extraction (PRD FR-16).

Pulls URLs from markdown links, bare URLs, and ``Source:`` lines, normalizes to
a bare hostname (``www.`` stripped), dedupes per question, and flags
brand-owned domains.
"""

from __future__ import annotations

import re

from aeo.analysis.models import CitationRecord

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s)<>\]\"']+")


def domain_of(url: str) -> str:
    """Bare hostname of a URL, lowercased, without ``www.`` or trailing punctuation."""
    host = re.sub(r"^https?://", "", url.strip()).split("/")[0].split("?")[0]
    host = host.split("@")[-1].split(":")[0].lower().strip().rstrip(".,);]")
    return host.removeprefix("www.")


def extract_urls(text: str) -> list[str]:
    """All URLs in document order (markdown hrefs first, then remaining bare)."""
    urls: list[str] = []
    seen: set[str] = set()
    for m in _MD_LINK_RE.finditer(text):
        u = m.group(1).rstrip(".,);]")
        if u not in seen:
            seen.add(u)
            urls.append(u)
    for m in _BARE_URL_RE.finditer(text):
        u = m.group(0).rstrip(".,);]")
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def _is_brand_owned(domain: str, brand_domain: str | None) -> bool:
    if not brand_domain:
        return False
    return domain == brand_domain or domain.endswith(f".{brand_domain}")


def extract_citations(
    segments: dict[int, str], brand_domain: str | None
) -> list[CitationRecord]:
    """Extract citations across segments, deduped by (question_index, domain)."""
    citations: list[CitationRecord] = []
    seen: set[tuple[int | None, str]] = set()
    for q_index, text in sorted(segments.items()):
        idx: int | None = q_index if q_index != 0 else None
        for url in extract_urls(text):
            domain = domain_of(url)
            if not domain:
                continue
            key = (idx, domain)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                CitationRecord(
                    domain=domain,
                    url=url,
                    question_index=idx,
                    brand_owned=_is_brand_owned(domain, brand_domain),
                )
            )
    return citations
