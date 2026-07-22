"""JSON report: the full structured run for programmatic use (PRD FR-22)."""

from __future__ import annotations

import json
from pathlib import Path

from aeo.schemas.run import RunRecord


def write_json(record: RunRecord, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
