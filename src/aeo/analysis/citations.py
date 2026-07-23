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
    """Bare hostname of a URL, lowercased, without ``www.`` or trailing punctuation.
    Subdomains are preserved (help.datacebo.com stays distinct from datacebo.com)."""
    host = re.sub(r"^https?://", "", url.strip()).split("/")[0].split("?")[0]
    host = host.split("@")[-1].split(":")[0].lower().strip().rstrip(".,);]")
    return host.removeprefix("www.")


def path_of(url: str) -> str:
    """Path portion of a URL (without query/fragment), '' for root."""
    after = re.sub(r"^https?://[^/]+", "", url.strip(), count=1)
    path = after.split("?")[0].split("#")[0].rstrip(".,);]")
    return "" if path in ("", "/") else path


def registrable_domain(host: str) -> str:
    """eTLD+1 heuristic — last two labels (datacebo.com from help.datacebo.com).
    Handles common two-part public suffixes (co.uk, com.au, ...)."""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    two_part = {"co", "com", "org", "net", "gov", "edu", "ac"}
    if labels[-2] in two_part and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


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
    segments: dict[int, str],
    brand_domain: str | None,
    reference_domains: list[str] | None = None,
) -> list[CitationRecord]:
    """Extract citations across segments, deduped by (question_index, domain)."""
    refs = set(reference_domains or [])
    citations: list[CitationRecord] = []
    seen: set[tuple[int | None, str]] = set()
    for q_index, text in sorted(segments.items()):
        idx: int | None = q_index if q_index != 0 else None
        for url in extract_urls(text):
            domain = domain_of(url)
            if not domain:
                continue
            path = path_of(url)
            # Dedup at the page level so distinct URLs on the same domain are kept.
            key = (idx, domain + path)
            if key in seen:
                continue
            seen.add(key)
            registrable = registrable_domain(domain)
            citations.append(
                CitationRecord(
                    domain=domain,
                    url=url,
                    path=path,
                    registrable=registrable,
                    is_subdomain=domain != registrable,
                    is_root=path == "",
                    question_index=idx,
                    brand_owned=_is_brand_owned(domain, brand_domain),
                    is_reference=domain in refs or any(
                        domain == r or domain.endswith(f".{r}") for r in refs
                    ),
                )
            )
    return citations
