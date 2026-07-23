"""Generate report artifacts for a run and record their paths."""

from __future__ import annotations

from aeo.logging import get_logger
from aeo.reports import write_csv, write_json, write_pdf, write_xlsx
from aeo.schemas.run import RunRecord
from aeo.storage import RunStore

log = get_logger(__name__)


def generate_reports(record: RunRecord, store: RunStore) -> dict[str, str]:
    """Write XLSX, CSV, JSON, and PDF into the run folder; return {format: path}."""
    run_dir = store.run_dir(record.id)
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "xlsx": str(write_xlsx(record, run_dir / "report.xlsx")),
        "csv": str(write_csv(record, run_dir / "report.csv")),
        "json": str(write_json(record, run_dir / "report.json")),
    }
    # PDF is heavier (charts); never let a failure abort the run's other artifacts.
    try:
        paths["pdf"] = str(write_pdf(record, run_dir / "report.pdf"))
    except Exception as exc:  # best-effort visual deliverable
        log.warning("pdf_report_failed", error=str(exc))
    return paths
