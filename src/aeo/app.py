"""FastAPI application factory.

Serves the REST API under ``/api`` and the prebuilt React SPA (or a placeholder)
as static files, so a single process yields one URL (PRD §6.1).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from aeo import __app_name__, __version__
from aeo.api.router import api_router
from aeo.constants import API_PREFIX, WEB_DIST_DIR
from aeo.logging import configure_logging, get_logger
from aeo.settings import get_settings
from aeo.storage import RunStore

log = get_logger(__name__)

_PLACEHOLDER_HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{__app_name__}</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#0b0f17;color:#e6edf3;
  display:grid;place-items:center;height:100vh;margin:0;text-align:center}}
 code{{background:#161b22;padding:2px 6px;border-radius:6px}}
 a{{color:#58a6ff}}
</style></head><body><main>
<h1>{__app_name__}</h1>
<p>The API is running. The web UI has not been built yet.</p>
<p>API docs: <a href="/docs">/docs</a> &middot; Health:
   <a href="/api/health">/api/health</a></p>
<p>Build the UI with <code>make build</code> (or it ships prebuilt in releases).</p>
</main></body></html>"""


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    RunStore.from_settings(settings).ensure()
    log.info("startup", app=__app_name__, version=__version__)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=__app_name__,
        version=__version__,
        description="Open-source AI brand-visibility scanner.",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://{settings.host}:{settings.port}", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=API_PREFIX)
    _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    """Serve the SPA with client-side-routing fallback to index.html."""
    dist = WEB_DIST_DIR
    index = dist / "index.html"
    assets = dist / "assets"

    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa(full_path: str, request: Request) -> FileResponse | HTMLResponse:
        # Never shadow the API or docs.
        if full_path.startswith(("api/", "docs", "openapi.json", "redoc")):
            return HTMLResponse("Not found", status_code=404)
        candidate = dist / full_path
        if full_path and candidate.is_file() and dist in candidate.resolve().parents:
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(_PLACEHOLDER_HTML)
