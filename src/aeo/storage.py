"""Filesystem-backed run storage.

Each run is a self-contained folder under ``{data_dir}/runs/{run_id}/``::

    data/runs/<run_id>/
        run.json          # full structured record (profile, questions, responses, metrics)
        report.xlsx       # generated artifacts (added during the reporting stage)
        report.csv
        report.json

There is no database: ``run.json`` is the source of truth, listing is a directory
scan, and re-downloading a report is just reading a file. Writes are atomic
(temp file + ``os.replace``) so a crash never leaves a half-written record.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from aeo.settings import Settings, get_settings

RUN_RECORD = "run.json"


class RunStore:
    """CRUD over on-disk run folders. Operates on plain JSON-able dicts;
    typed Pydantic schemas wrap this in the services layer (Step 2)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> RunStore:
        settings = settings or get_settings()
        return cls(settings.runs_path)

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def artifact_path(self, run_id: str, filename: str) -> Path:
        return self.run_dir(run_id) / filename

    def exists(self, run_id: str) -> bool:
        return (self.run_dir(run_id) / RUN_RECORD).is_file()

    def save_run(self, record: dict[str, Any]) -> None:
        """Persist a run record. ``record['id']`` selects the folder."""
        run_id = record["id"]
        self.run_dir(run_id).mkdir(parents=True, exist_ok=True)
        self.write_json(run_id, RUN_RECORD, record)

    def load_run(self, run_id: str) -> dict[str, Any]:
        return self.read_json(run_id, RUN_RECORD)

    def list_run_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            p.name for p in self.root.iterdir() if (p / RUN_RECORD).is_file()
        )

    def list_runs(self) -> list[dict[str, Any]]:
        """Load every run record. Fine at self-hosted scale (dozens to hundreds)."""
        runs = [self.load_run(rid) for rid in self.list_run_ids()]
        runs.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
        return runs

    def delete_run(self, run_id: str) -> None:
        shutil.rmtree(self.run_dir(run_id), ignore_errors=True)

    # --- low-level JSON helpers (atomic) ---

    def write_json(self, run_id: str, name: str, data: Any) -> Path:
        target = self.run_dir(run_id) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        finally:
            Path(tmp).unlink(missing_ok=True)
        return target

    def read_json(self, run_id: str, name: str) -> dict[str, Any]:
        text = (self.run_dir(run_id) / name).read_text(encoding="utf-8")
        result: dict[str, Any] = json.loads(text)
        return result
