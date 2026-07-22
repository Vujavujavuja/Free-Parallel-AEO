#!/usr/bin/env python3
"""Free-Parallel-AEO single entrypoint.

A dependency-free bootstrapper (stdlib only) that provisions everything and then
hands off to the ``aeo`` Typer CLI. Usage::

    python run.py                       # bootstrap + serve the UI
    python run.py scan --company x.yaml # headless run
    python run.py doctor                # diagnostics
    python run.py serve --port 8080

Steps: preflight -> ensure .env -> provision venv+deps (idempotent) -> ensure
data dirs -> build frontend if needed -> launch. It re-executes itself inside
the project virtualenv once dependencies are available. Runs are stored as
folders under ./data/runs/ — there is no database to migrate.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
MIN_PYTHON = (3, 11)
_REEXEC_FLAG = "AEO_BOOTSTRAPPED"


def _log(msg: str) -> None:
    print(f"[run.py] {msg}", flush=True)


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def preflight() -> None:
    if sys.version_info < MIN_PYTHON:
        have = ".".join(map(str, sys.version_info[:3]))
        _log(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {have}.")
        sys.exit(1)


def ensure_env_file() -> None:
    env = ROOT / ".env"
    example = ROOT / ".env.example"
    if env.exists():
        return
    if example.exists():
        shutil.copyfile(example, env)
        _log(f"Created {env.name} from {example.name}.")
    else:
        env.write_text("OPENROUTER_API_KEY=\n", encoding="utf-8")
        _log("Created a blank .env.")
    _log("=> Edit .env and set OPENROUTER_API_KEY before running a scan.")


def _deps_available(python: Path | str) -> bool:
    probe = "import fastapi, typer, aeo"
    result = subprocess.run(
        [str(python), "-c", probe], capture_output=True, cwd=ROOT
    )
    return result.returncode == 0


def ensure_environment() -> Path:
    """Provision the project venv with dependencies. Idempotent. Returns interpreter."""
    target = _venv_python()
    if target.exists() and _deps_available(target):
        return target

    uv = shutil.which("uv")
    if not VENV_DIR.exists():
        _log("Creating virtual environment (.venv)...")
        if uv:
            subprocess.check_call([uv, "venv", str(VENV_DIR)], cwd=ROOT)
        else:
            subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    _log("Installing dependencies (this runs once)...")
    if uv:
        subprocess.check_call(
            [uv, "pip", "install", "--python", str(target), "-e", "."], cwd=ROOT
        )
    else:
        subprocess.check_call(
            [str(target), "-m", "pip", "install", "--upgrade", "pip"], cwd=ROOT
        )
        subprocess.check_call([str(target), "-m", "pip", "install", "-e", "."], cwd=ROOT)
    return target


def ensure_data_dirs() -> None:
    """Create the on-disk run storage directories (no database)."""
    (ROOT / "data" / "runs").mkdir(parents=True, exist_ok=True)


def ensure_frontend(python: Path) -> None:
    dist_index = ROOT / "src" / "aeo" / "web" / "dist" / "index.html"
    if dist_index.exists():
        return
    frontend = ROOT / "frontend"
    npm = shutil.which("npm")
    if frontend.exists() and npm:
        _log("Building frontend (dist missing)...")
        try:
            subprocess.check_call([npm, "install"], cwd=frontend)
            subprocess.check_call([npm, "run", "build"], cwd=frontend)
        except subprocess.CalledProcessError:
            _log("Frontend build failed — a placeholder page will be served.")
    else:
        _log("No prebuilt frontend and Node unavailable — placeholder page will serve.")


def launch(python: Path, args: list[str]) -> int:
    # Delegate any explicit CLI command straight to the aeo CLI.
    if args:
        return subprocess.call([str(python), "-m", "aeo", *args], cwd=ROOT)

    # No args: serve + open browser.
    host = os.environ.get("HOST", "127.0.0.1")
    port = os.environ.get("PORT", "8000")
    url = f"http://{host}:{port}"
    _log(f"Starting server at {url}")
    with contextlib.suppress(Exception):
        webbrowser.open(url)
    return subprocess.call([str(python), "-m", "aeo", "serve"], cwd=ROOT)


def main() -> int:
    preflight()
    args = sys.argv[1:]
    ensure_env_file()

    # Fast path: if the *current* interpreter already has deps (e.g. developer
    # venv, Docker), skip provisioning entirely.
    if _deps_available(sys.executable):
        python = Path(sys.executable)
    else:
        python = ensure_environment()
        if Path(python).resolve() != Path(sys.executable).resolve() and not os.environ.get(
            _REEXEC_FLAG
        ):
            os.environ[_REEXEC_FLAG] = "1"
            return subprocess.call([str(python), str(ROOT / "run.py"), *args], cwd=ROOT)

    ensure_data_dirs()
    if not args or args[0] in {"serve"}:
        ensure_frontend(python)
    return launch(python, args)


if __name__ == "__main__":
    raise SystemExit(main())
