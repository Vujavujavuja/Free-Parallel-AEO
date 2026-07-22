"""Generate report artifacts for a run and record their paths."""

from __future__ import annotations

from aeo.reports import write_csv, write_json, write_xlsx
from aeo.schemas.run import RunRecord
from aeo.storage import RunStore

_FILENAMES = {"xlsx": "report.xlsx", "csv": "report.csv", "json": "report.json"}


def generate_reports(record: RunRecord, store: RunStore) -> dict[str, str]:
    """Write XLSX, CSV, and JSON into the run folder; return {format: path}."""
    run_dir = store.run_dir(record.id)
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "xlsx": write_xlsx(record, run_dir / _FILENAMES["xlsx"]),
        "csv": write_csv(record, run_dir / _FILENAMES["csv"]),
        "json": write_json(record, run_dir / _FILENAMES["json"]),
    }
    return {fmt: str(p) for fmt, p in paths.items()}
