"""Load and validate company profiles from YAML or JSON files (PRD FR-1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from aeo.schemas.company import CompanyProfile


def load_company(path: Path) -> CompanyProfile:
    text = path.read_text(encoding="utf-8")
    data: Any
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        # Try YAML (a superset of JSON) as a permissive fallback.
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Company profile in {path} must be a mapping/object.")
    return CompanyProfile.model_validate(data)
