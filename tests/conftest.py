"""Shared test fixtures."""

from __future__ import annotations

import pytest

from aeo.schemas.company import CompanyProfile
from aeo.schemas.run import RunOptions


@pytest.fixture
def company() -> CompanyProfile:
    return CompanyProfile(
        name="Acme Synthetic Data",
        website="https://acme.com",
        category="Synthetic data platform",
        products=["Acme SDK"],
        competitors=["Gretel", "Tonic"],
        aliases=["Acme"],
    )


@pytest.fixture
def stub_options() -> RunOptions:
    return RunOptions(
        orchestrator_model="stub/orchestrator",
        target_models=["openai/gpt-stub", "anthropic/claude-stub", "google/gemini-stub"],
        question_count=6,
    )
