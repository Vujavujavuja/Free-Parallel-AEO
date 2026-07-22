"""Company profile schema (PRD FR-1..FR-3)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_COMPETITORS = 20


class SourceDocument(BaseModel):
    """A user-uploaded document (docx/pdf/md/txt) parsed to text, fed to the
    orchestrator as extra context."""

    name: str
    text: str


def _domain_of(raw: str) -> str:
    host = re.sub(r"^https?://", "", raw.strip()).split("/")[0].split("?")[0]
    return host.split("@")[-1].split(":")[0].lower().strip().rstrip(".,);]").removeprefix("www.")


class CompanyProfile(BaseModel):
    """The subject of a scan. Aliases are auto-seeded from name + domain."""

    name: str = Field(min_length=1)
    website: str | None = None
    description: str | None = None
    category: str | None = None
    products: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list, max_length=MAX_COMPETITORS)
    aliases: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    notes: str | None = None
    # Sites to track in reference/citation counting (stored as normalized domains).
    reference_sites: list[str] = Field(default_factory=list)
    # Uploaded documents (parsed to text) used as orchestrator context.
    source_documents: list[SourceDocument] = Field(default_factory=list)

    @field_validator("website")
    @classmethod
    def _normalize_website(cls, v: str | None) -> str | None:
        if not v:
            return v
        v = v.strip()
        if v and not re.match(r"^https?://", v):
            v = f"https://{v}"
        return v

    @field_validator("competitors")
    @classmethod
    def _cap_competitors(cls, v: list[str]) -> list[str]:
        cleaned = [c.strip() for c in v if c.strip()]
        return cleaned[:MAX_COMPETITORS]

    @field_validator("reference_sites")
    @classmethod
    def _normalize_reference_sites(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in v:
            dom = _domain_of(item)
            if dom and dom not in seen:
                seen.add(dom)
                out.append(dom)
        return out

    @property
    def domain(self) -> str | None:
        if not self.website:
            return None
        return _domain_of(self.website) or None

    @property
    def reference_domains(self) -> list[str]:
        return self.reference_sites

    @model_validator(mode="after")
    def _seed_aliases(self) -> CompanyProfile:
        """Ensure the brand name and domain are present in the alias list."""
        seeds: list[str] = [self.name]
        domain = self.domain
        if domain:
            seeds.append(domain)
            root = domain.split(".")[0]
            if root and root != domain:
                seeds.append(root)
        merged = list(self.aliases)
        lowered = {a.lower() for a in merged}
        for s in seeds:
            if s and s.lower() not in lowered:
                merged.append(s)
                lowered.add(s.lower())
        self.aliases = merged
        return self

    @property
    def brand_terms(self) -> list[str]:
        """All strings that count as a brand mention (name + aliases + products)."""
        terms: list[str] = []
        seen: set[str] = set()
        for t in [self.name, *self.aliases, *self.products]:
            key = t.lower().strip()
            if key and key not in seen:
                seen.add(key)
                terms.append(t)
        return terms
