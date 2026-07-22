"""CSV report: long format (one row per model answer) (PRD FR-22)."""

from __future__ import annotations

import csv
from pathlib import Path

from aeo.reports.base import get_analysis, sanitize_cell
from aeo.schemas.run import RunRecord

_HEADER = [
    "model",
    "provider",
    "question_index",
    "brand_mentions",
    "web_search_used",
    "provenance",
    "content",
]


def write_csv(record: RunRecord, path: Path) -> Path:
    analysis = get_analysis(record)
    by_model = {ma.model_id: ma for ma in analysis.models}
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        for r in record.responses:
            ma = by_model.get(r.model_id)
            writer.writerow(
                [
                    sanitize_cell(r.model_id),
                    sanitize_cell(r.model_id.split("/")[0] if "/" in r.model_id else ""),
                    r.question_index if r.question_index is not None else "all",
                    ma.brand_mentions if ma else "",
                    r.web_search_used,
                    ma.provenance.value if ma else "",
                    sanitize_cell(r.content),
                ]
            )
    return path
