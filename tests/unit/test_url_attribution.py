"""Tests for URL-level attribution (root/subdomain/path)."""

from __future__ import annotations

from aeo.analysis.citations import extract_citations, path_of, registrable_domain


def test_registrable_domain() -> None:
    assert registrable_domain("datacebo.com") == "datacebo.com"
    assert registrable_domain("help.datacebo.com") == "datacebo.com"
    assert registrable_domain("cookbooks.datacebo.com") == "datacebo.com"
    assert registrable_domain("docs.example.co.uk") == "example.co.uk"


def test_path_of() -> None:
    assert path_of("https://datacebo.com") == ""
    assert path_of("https://datacebo.com/") == ""
    assert path_of("https://datacebo.com/sdv-enterprise?utm=x") == "/sdv-enterprise"


def test_subdomain_and_page_classification() -> None:
    segs = {
        1: (
            "Root https://datacebo.com , page https://datacebo.com/pricing , "
            "subdomain https://help.datacebo.com/setup"
        )
    }
    cites = {c.domain + c.path: c for c in extract_citations(segs, brand_domain="datacebo.com")}

    root = cites["datacebo.com"]
    assert root.is_root and not root.is_subdomain and root.brand_owned

    page = cites["datacebo.com/pricing"]
    assert not page.is_root and page.path == "/pricing" and page.brand_owned

    sub = cites["help.datacebo.com/setup"]
    assert sub.is_subdomain and sub.registrable == "datacebo.com" and sub.brand_owned
