"""Hintergrund-Scheduler: holt regelmäßig neue Nachrichten (macht die Seite live).

Läuft als asyncio-Task im App-Prozess, wenn ``INGEST_INTERVAL_MINUTES > 0``.
Die eigentliche Ingestion ist blockierend (Netz + DB) und läuft daher in einem
Thread. Fehler einzelner Läufe werden geloggt, brechen die Schleife aber nicht ab.

Hinweis: Bei mehreren App-Maschinen laufen mehrere Scheduler – das ist unkritisch,
weil die Ingestion Duplikate über URL/Titel-Hash herausfiltert. Für großen
Maßstab die Ingestion auf eine dedizierte Maschine auslagern.
"""
from __future__ import annotations

import asyncio

from app.config import settings


def _ingestieren() -> None:
    from app.database import SessionLocal
    from app.feeds import DEFAULT_FEEDS
    from app.services.news import fetch_and_ingest

    db = SessionLocal()
    try:
        ergebnis = fetch_and_ingest(db, DEFAULT_FEEDS)
        print(f"[scheduler] Ingestion abgeschlossen: {ergebnis}")
    finally:
        db.close()


async def ingest_loop() -> None:
    """Führt die Ingestion sofort und danach im konfigurierten Intervall aus."""
    intervall = max(1, settings.ingest_interval_minutes) * 60
    while True:
        try:
            await asyncio.to_thread(_ingestieren)
        except Exception as exc:  # pragma: no cover - Netz-/Laufzeitabhängig
            print(f"[scheduler] Ingestion-Fehler: {exc}")
        await asyncio.sleep(intervall)
