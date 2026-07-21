#!/usr/bin/env python3
"""Standalone environment provisioner.

`run.py` inlines the same steps for a truly single-file entrypoint; this script
exposes them for CI / manual use::

    python scripts/bootstrap.py          # venv + deps + migrate + frontend
    python scripts/bootstrap.py --no-frontend
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_run_module() -> object:
    spec = importlib.util.spec_from_file_location("_aeo_run", ROOT / "run.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    run = _load_run_module()
    run.preflight()  # type: ignore[attr-defined]
    run.ensure_env_file()  # type: ignore[attr-defined]
    python = run.ensure_environment()  # type: ignore[attr-defined]
    run.run_migrations(python)  # type: ignore[attr-defined]
    if "--no-frontend" not in argv:
        run.ensure_frontend(python)  # type: ignore[attr-defined]
    print("[bootstrap] Environment ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
