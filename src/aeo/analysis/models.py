"""Typed analysis result models (serialized into ``run.json['analysis']``)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aeo.constants import Provenance


class CitationRecord(BaseModel):
    domain: str  # full host, www stripped (subdomains preserved, e.g. help.datacebo.com)
    url: str
    path: str = ""  # URL path (which page)
    registrable: str = ""  # eTLD+1, e.g. datacebo.com
    is_subdomain: bool = False  # host is a subdomain of the registrable domain
    is_root: bool = True  # points at the root, not a specific page
    question_index: int | None = None
    brand_owned: bool = False
    is_reference: bool = False  # matches a user-provided reference site
    is_search: bool = False  # sourced from a web-search annotation


class ModelAnalysis(BaseModel):
    model_id: str
    provider: str = ""
    web_search_used: bool = False
    num_searches: int = 0
    search_queries: list[str] = Field(default_factory=list)
    brand_mentions: int = 0
    subbrand_mentions: int = 0
    in_vendor_table: bool = False
    questions_mentioning: int = 0
    per_question_brand: dict[int, int] = Field(default_factory=dict)
    competitor_totals: dict[str, int] = Field(default_factory=dict)
    citations: list[CitationRecord] = Field(default_factory=list)
    unique_domains: list[str] = Field(default_factory=list)
    # Self-reported per question: {q_index: {"cited": [...], "named": [...]}}
    self_reported: dict[int, dict[str, list[str]]] = Field(default_factory=dict)
    reference_citations: int = 0  # citations to user-provided reference sites
    answer_length: int = 0
    provenance: Provenance = Provenance.ABSENT
    error: str | None = None


class QuestionAggregate(BaseModel):
    index: int
    text: str
    total_mentions: int = 0
    models_mentioning: int = 0
    avg_per_model: float = 0.0
    peak_model: str = ""
    interpretation: str = ""


class DomainStat(BaseModel):
    domain: str
    num_models: int
    models: list[str]
    brand_owned: bool = False
    is_reference: bool = False


class UrlStat(BaseModel):
    """URL-level attribution: which exact page/subdomain is cited."""

    url: str
    host: str
    path: str
    registrable: str
    kind: str  # "root" | "subdomain" | "page"
    num_models: int
    models: list[str]
    brand_owned: bool = False
    is_reference: bool = False


class AnalysisResult(BaseModel):
    models: list[ModelAnalysis] = Field(default_factory=list)
    question_indices: list[int] = Field(default_factory=list)
    questions: list[QuestionAggregate] = Field(default_factory=list)
    # heatmap[model_id][question_index] = brand mention count
    heatmap: dict[str, dict[int, int]] = Field(default_factory=dict)
    competitors: list[str] = Field(default_factory=list)
    # competitor_sov[model_id][competitor] = mention count
    competitor_sov: dict[str, dict[str, int]] = Field(default_factory=dict)
    domain_frequency: list[DomainStat] = Field(default_factory=list)
    url_frequency: list[UrlStat] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    quotes: list[dict[str, str]] = Field(default_factory=list)
    # AI-written, brand-specific actions to improve visibility (synthesis pass).
    recommendations: list[str] = Field(default_factory=list)

    def ranked_models(self) -> list[ModelAnalysis]:
        """Models ranked by brand visibility (mentions, then questions covered)."""
        return sorted(
            self.models,
            key=lambda m: (m.brand_mentions, m.questions_mentioning),
            reverse=True,
        )
