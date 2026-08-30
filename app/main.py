"""FastAPI-Einstiegspunkt für ParteiWiki."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.web.routes import router as web_router

app = FastAPI(
    title="ParteiWiki",
    version=__version__,
    description=(
        "Neutrale, quellenbasierte Wissensplattform pro Partei. "
        "Gleiche Methodik für alle Parteien – keine Sonderfälle."
    ),
)

app.include_router(api_router)
app.include_router(web_router)

_static = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static)), name="static")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
