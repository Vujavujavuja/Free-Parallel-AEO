"""Company profile schema (PRD FR-1..FR-3)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator


class CompanyProfile(BaseModel):
    """The subject of a scan. Aliases are auto-seeded from name + domain."""

    name: str = Field(min_length=1)
    website: str | None = None
    description: str | None = None
    category: str | None = None
    products: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    icp: str | None = Field(default=None, description="Ideal customer profile / target buyer.")
    regions: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("website")
    @classmethod
    def _normalize_website(cls, v: str | None) -> str | None:
        if not v:
            return v
        v = v.strip()
        if v and not re.match(r"^https?://", v):
            v = f"https://{v}"
        return v

    @property
    def domain(self) -> str | None:
        """Bare hostname of the website, lowercased, without ``www.``."""
        if not self.website:
            return None
        host = re.sub(r"^https?://", "", self.website).split("/")[0].lower()
        return host.removeprefix("www.") or None

    @model_validator(mode="after")
    def _seed_aliases(self) -> CompanyProfile:
        """Ensure the brand name and domain are present in the alias list."""
        seeds: list[str] = [self.name]
        domain = self.domain
        if domain:
            seeds.append(domain)
            # e.g. "acme.com" -> "acme"
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
