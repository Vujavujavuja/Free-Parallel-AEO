"""Enable `python -m aeo` to invoke the Typer CLI."""

from __future__ import annotations

from aeo.cli import app

if __name__ == "__main__":
    app()
