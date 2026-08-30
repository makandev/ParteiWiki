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


async def _mdb_sync_beim_start() -> None:
    """Einmaliger MdB- und Umfrage-Abgleich beim Start (Thread, fail-soft)."""
    def _lauf() -> None:
        from app.database import SessionLocal
        from app.services.mandate_sync import sync_mdb_still
        from app.services.umfrage_sync import sync_umfragen_still

        db = SessionLocal()
        try:
            ergebnis = sync_mdb_still(db)
            if ergebnis is not None:
                print(f"[app] MdB-Abgleich: {ergebnis}")
            umfrage = sync_umfragen_still(db)
            if umfrage is not None:
                print(f"[app] Umfrage-Abgleich: {umfrage}")
        finally:
            db.close()

    await asyncio.to_thread(_lauf)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startet optional den Auto-Ingestion-Scheduler (macht die Seite live)."""
    # Referenzen halten: der Event-Loop hält nur schwache Referenzen auf Tasks,
    # ein fire-and-forget-Task könnte sonst mitten im Lauf vom GC eingesammelt
    # werden.
    tasks: list[asyncio.Task] = []
    if settings.mdb_sync_beim_start:
        tasks.append(asyncio.create_task(_mdb_sync_beim_start()))
    if settings.ingest_interval_minutes > 0:
        from app.services.scheduler import ingest_loop

        tasks.append(asyncio.create_task(ingest_loop()))
        print(f"[app] Auto-Ingestion aktiv (alle {settings.ingest_interval_minutes} min).")
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


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
