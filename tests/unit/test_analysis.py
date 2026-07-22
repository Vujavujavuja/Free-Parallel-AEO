"""Unit tests for the pure analysis functions (PRD FR-14..FR-20)."""

from __future__ import annotations

from aeo.analysis.citations import domain_of, extract_citations
from aeo.analysis.mentions import count_term, in_vendor_table, mentions_present
from aeo.analysis.queries import parse_query_traces
from aeo.analysis.segmenter import segment


def test_segment_various_headers() -> None:
    text = "preamble here\nQ1. first\nbody1\n## Q2 second\nbody2\n**Q3.** third\nbody3"
    segs = segment(text)
    assert segs[0] == "preamble here"
    assert "body1" in segs[1]
    assert "body2" in segs[2]
    assert "body3" in segs[3]


def test_segment_no_headers_is_preamble() -> None:
    assert segment("just some text") == {0: "just some text"}


def test_count_term_word_boundary() -> None:
    assert count_term("Acme is great, Acme rocks", "Acme") == 2
    # Should not match inside another word.
    assert count_term("Acmex Acmely", "Acme") == 0
    # Case-insensitive.
    assert count_term("acme ACME", "Acme") == 2


def test_mentions_present() -> None:
    assert mentions_present("we like Gretel", ["Gretel", "Tonic"])
    assert not mentions_present("nothing here", ["Gretel"])


def test_in_vendor_table() -> None:
    md = "| Vendor | Score |\n| Acme | 9 |"
    assert in_vendor_table(md, ["Acme"])
    assert not in_vendor_table("Acme is nice prose.", ["Acme"])


def test_domain_extraction_and_brand_owned() -> None:
    assert domain_of("https://www.g2.com/products/acme") == "g2.com"
    segs = {1: "See [docs](https://acme.com/docs) and https://g2.com/x"}
    cites = extract_citations(segs, brand_domain="acme.com")
    domains = {c.domain: c.brand_owned for c in cites}
    assert domains["acme.com"] is True
    assert domains["g2.com"] is False


def test_dedupe_per_question() -> None:
    segs = {1: "https://g2.com/a https://g2.com/b https://www.g2.com/c"}
    cites = extract_citations(segs, brand_domain=None)
    assert [c.domain for c in cites] == ["g2.com"]


def test_reference_site_flagging() -> None:
    segs = {1: "See https://g2.com/x and https://acme.com/docs and https://random.io"}
    cites = extract_citations(segs, brand_domain="acme.com", reference_domains=["g2.com"])
    flags = {c.domain: c.is_reference for c in cites}
    assert flags["g2.com"] is True
    assert flags["acme.com"] is False
    assert flags["random.io"] is False


def test_query_trace_parsing() -> None:
    content = "Searched for: acme reviews\nSome answer\nSearched for best alternatives"
    queries = parse_query_traces(content)
    assert "acme reviews" in queries
    assert any("alternatives" in q for q in queries)
