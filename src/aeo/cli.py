"""Typer command-line interface.

Commands (PRD FR-27): scan, runs list, runs show, report, models, serve, doctor.
In the skeleton milestone only ``doctor`` and ``serve`` are fully wired; the
pipeline commands are filled in during Step 2.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from aeo import __app_name__, __version__
from aeo.logging import configure_logging
from aeo.settings import get_settings

app = typer.Typer(
    name="aeo",
    help=f"{__app_name__} — AI brand-visibility scanner.",
    no_args_is_help=True,
    add_completion=False,
)
runs_app = typer.Typer(name="runs", help="Inspect past runs.", no_args_is_help=True)
app.add_typer(runs_app)

_NOT_IMPLEMENTED = "This command is implemented in Step 2 (backend). Skeleton stub."


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True,
                     help="Show version and exit."),
    ] = False,
) -> None:
    """Root callback; configures logging for every invocation."""
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command()
def doctor() -> None:
    """Environment & key diagnostics (PRD §13)."""
    settings = get_settings()
    ok = True

    def check(label: str, passed: bool, detail: str) -> None:
        nonlocal ok
        ok = ok and passed
        mark = "✓" if passed else "✗"
        typer.echo(f"  {mark} {label}: {detail}")

    typer.echo(f"{__app_name__} doctor")
    py_ok = sys.version_info >= (3, 11)
    check("Python >= 3.11", py_ok, ".".join(map(str, sys.version_info[:3])))
    check("OPENROUTER_API_KEY", settings.has_api_key,
          "set" if settings.has_api_key else "MISSING — add it to .env")
    check("Database URL", True, settings.database_url)
    check("Orchestrator model", True, settings.orchestrator_model)
    check("Target panel size", True, f"{len(settings.target_models)} models")
    typer.echo("")
    if ok:
        typer.secho("All checks passed.", fg=typer.colors.GREEN)
    else:
        typer.secho("Some checks failed — see above.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Bind host.")] = None,
    port: Annotated[int | None, typer.Option(help="Bind port.")] = None,
    reload: Annotated[bool, typer.Option(help="Auto-reload (dev).")] = False,
) -> None:
    """Serve the REST API and the web UI (single process)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aeo.app:create_app",
        factory=True,
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
    )


@app.command()
def models() -> None:
    """List available OpenRouter models for panel selection."""
    typer.secho(_NOT_IMPLEMENTED, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@app.command()
def scan(
    company: Annotated[Path, typer.Option(help="Company profile YAML/JSON.")],
    out: Annotated[Path, typer.Option(help="Output directory for reports.")] = Path(
        "./reports"
    ),
    models_arg: Annotated[
        str | None, typer.Option("--models", help="Comma list or @panel-default.")
    ] = None,
) -> None:
    """Run a full scan headlessly and write report artifacts."""
    _ = (company, out, models_arg)
    typer.secho(_NOT_IMPLEMENTED, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@app.command()
def report(
    run_id: Annotated[str, typer.Argument(help="Run id.")],
    fmt: Annotated[str, typer.Option("--format", help="xlsx | csv | json.")] = "xlsx",
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("./reports"),
) -> None:
    """Regenerate/download a report artifact for an existing run."""
    _ = (run_id, fmt, out)
    typer.secho(_NOT_IMPLEMENTED, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@runs_app.command("list")
def runs_list() -> None:
    """List runs with status and cost."""
    typer.secho(_NOT_IMPLEMENTED, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


@runs_app.command("show")
def runs_show(run_id: Annotated[str, typer.Argument(help="Run id.")]) -> None:
    """Show full detail for a run."""
    _ = run_id
    typer.secho(_NOT_IMPLEMENTED, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
