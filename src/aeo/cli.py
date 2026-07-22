"""Typer command-line interface (PRD FR-27): scan, runs list/show, report,
models, serve, doctor."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer

from aeo import __app_name__, __version__
from aeo.constants import PromptMode, RunStatus
from aeo.logging import configure_logging, get_logger
from aeo.settings import get_settings
from aeo.storage import RunStore

log = get_logger(__name__)

app = typer.Typer(
    name="aeo",
    help=f"{__app_name__} — AI brand-visibility scanner.",
    no_args_is_help=True,
    add_completion=False,
)
runs_app = typer.Typer(name="runs", help="Inspect past runs.", no_args_is_help=True)
app.add_typer(runs_app)


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
    configure_logging(get_settings().log_level)


@app.command()
def doctor() -> None:
    """Environment & key diagnostics (PRD §13)."""
    settings = get_settings()
    ok = True

    def check(label: str, passed: bool, detail: str) -> None:
        nonlocal ok
        ok = ok and passed
        typer.echo(f"  {'✓' if passed else '✗'} {label}: {detail}")

    typer.echo(f"{__app_name__} doctor")
    check("Python >= 3.11", sys.version_info >= (3, 11),
          ".".join(map(str, sys.version_info[:3])))
    check("OPENROUTER_API_KEY", settings.has_api_key,
          "set" if settings.has_api_key else "MISSING — add it to .env (or use --stub)")
    check("Run storage", True, str(settings.runs_path))
    check("Orchestrator model", True, settings.orchestrator_model)
    check("Target panel size", True, f"{len(settings.target_models)} models")
    typer.echo("")
    if ok:
        typer.secho("All checks passed.", fg=typer.colors.GREEN)
    else:
        typer.secho("Some checks failed — see above.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def models(
    stub: Annotated[bool, typer.Option(help="Use the offline stub provider.")] = False,
) -> None:
    """List available models (live OpenRouter catalog, or the stub panel)."""
    from aeo.providers import get_provider

    provider = get_provider("stub" if stub else "openrouter", get_settings())

    async def _run() -> None:
        try:
            catalog = await provider.list_models()
        finally:
            await provider.aclose()
        typer.echo(f"{len(catalog)} models:")
        for m in catalog[:200]:
            ctx = f"  ctx={m.context_length}" if m.context_length else ""
            typer.echo(f"  {m.id}{ctx}")

    asyncio.run(_run())


@app.command()
def scan(
    company: Annotated[Path, typer.Option(help="Company profile YAML/JSON.")],
    out: Annotated[Path, typer.Option(help="Copy reports to this directory.")] = Path(
        "./reports"
    ),
    models_opt: Annotated[
        str | None, typer.Option("--models", help="Comma-separated model ids.")
    ] = None,
    stub: Annotated[bool, typer.Option(help="Run offline with the stub provider ($0).")] = False,
    web_search: Annotated[bool, typer.Option(help="Enable OpenRouter web search.")] = False,
    per_question: Annotated[bool, typer.Option(help="One request per question.")] = False,
) -> None:
    """Run a full scan headlessly and write report artifacts."""
    from aeo.services import run_service
    from aeo.services.company_service import load_company

    settings = get_settings()
    if not stub and not settings.has_api_key:
        typer.secho(
            "No OPENROUTER_API_KEY set. Add it to .env, or run with --stub for a free demo.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    profile = load_company(company)
    target = (
        [m.strip() for m in models_opt.split(",") if m.strip()]
        if models_opt
        else None
    )
    if stub and not target:
        target = ["openai/gpt-stub", "anthropic/claude-stub", "google/gemini-stub",
                  "meta/llama-stub", "mistral/mistral-stub"]

    options = run_service.options_from_settings(settings, target_models=target)
    options.enable_web_search = web_search
    if per_question:
        options.prompt_mode = PromptMode.PER_QUESTION
    record = run_service.build_run(profile, options)

    typer.echo(f"Starting scan {record.id} for {profile.name} "
               f"({len(options.target_models)} models){' [stub]' if stub else ''}...")

    async def _emit(event: object) -> None:
        ev = event  # ProgressEvent
        detail = getattr(ev, "detail", "")
        completed = getattr(ev, "completed", 0)
        total = getattr(ev, "total", 0)
        status = getattr(ev, "status", "")
        suffix = f" [{completed}/{total}]" if total else ""
        typer.echo(f"  · {status}{suffix} {detail}")

    result = asyncio.run(
        run_service.execute_run(
            record,
            provider_name="stub" if stub else "openrouter",
            settings=settings,
            emit=_emit,
        )
    )

    if result.status == RunStatus.FAILED:
        typer.secho(f"Run failed: {result.error}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    _copy_reports(result.reports, out)
    typer.secho(
        f"\nDone. Run {result.id} · cost ${result.total_cost_usd:.4f} · "
        f"{len(result.questions)} questions x {len(options.target_models)} models.",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Reports: {out.resolve()}")


@app.command()
def report(
    run_id: Annotated[str, typer.Argument(help="Run id.")],
    fmt: Annotated[str, typer.Option("--format", help="xlsx | csv | json.")] = "xlsx",
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("./reports"),
) -> None:
    """Copy an existing run's report artifact to ``out``."""
    from aeo.services import run_service

    record = run_service.get_run(run_id)
    if fmt not in record.reports:
        typer.secho(f"No {fmt} report for run {run_id}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    _copy_reports({fmt: record.reports[fmt]}, out)
    typer.echo(f"Copied {fmt} report to {out.resolve()}")


@runs_app.command("list")
def runs_list() -> None:
    """List runs with status and cost."""
    from aeo.services import run_service

    summaries = run_service.list_runs()
    if not summaries:
        typer.echo("No runs yet.")
        return
    typer.echo(f"{'RUN ID':<14}{'STATUS':<22}{'COST':>9}  COMPANY")
    for s in summaries:
        typer.echo(
            f"{s.id:<14}{s.status.value:<22}${s.total_cost_usd:>7.4f}  {s.company_name}"
        )


@runs_app.command("show")
def runs_show(run_id: Annotated[str, typer.Argument(help="Run id.")]) -> None:
    """Show summary detail for a run."""
    from aeo.services import run_service

    r = run_service.get_run(run_id)
    typer.echo(f"Run {r.id} — {r.status.value}")
    typer.echo(f"  Company:   {r.company.name}")
    typer.echo(f"  Created:   {r.created_at}")
    typer.echo(f"  Models:    {len(r.options.target_models)}")
    typer.echo(f"  Questions: {len(r.questions)}")
    typer.echo(f"  Cost:      ${r.total_cost_usd:.4f}")
    if r.analysis:
        insights = r.analysis.get("insights", [])
        for line in insights:
            typer.echo(f"  • {line}")
    if r.reports:
        typer.echo(f"  Reports:   {', '.join(r.reports)}")


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Bind host.")] = None,
    port: Annotated[int | None, typer.Option(help="Bind port.")] = None,
    reload: Annotated[bool, typer.Option(help="Auto-reload (dev).")] = False,
) -> None:
    """Serve the REST API and the web UI (single process)."""
    import uvicorn

    settings = get_settings()
    RunStore.from_settings(settings).ensure()
    uvicorn.run(
        "aeo.app:create_app", factory=True,
        host=host or settings.host, port=port or settings.port, reload=reload,
    )


def _copy_reports(reports: dict[str, str], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for src in reports.values():
        src_path = Path(src)
        if src_path.is_file():
            shutil.copy2(src_path, out / src_path.name)


if __name__ == "__main__":
    app()
