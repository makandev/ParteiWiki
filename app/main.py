"""FastAPI-Einstiegspunkt für ParteiWiki."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.config import settings
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startet optional den Auto-Ingestion-Scheduler (macht die Seite live)."""
    task = None
    if settings.ingest_interval_minutes > 0:
        from app.services.scheduler import ingest_loop

        task = asyncio.create_task(ingest_loop())
        print(f"[app] Auto-Ingestion aktiv (alle {settings.ingest_interval_minutes} min).")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


app = FastAPI(
    title="ParteiWiki",
    version=__version__,
    description=(
        "Neutrale, quellenbasierte Wissensplattform pro Partei. "
        "Gleiche Methodik für alle Parteien – keine Sonderfälle."
    ),
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(web_router)

_static = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static)), name="static")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
