"""Lädt die konfigurierten Nachrichten-Feeds und verarbeitet sie.

Aufruf:  python -m scripts.ingest_news
Als Cron (z. B. stündlich):
    0 * * * *  cd /pfad/zu/ParteiWiki && python -m scripts.ingest_news
"""
from __future__ import annotations

from app.database import SessionLocal
from app.feeds import DEFAULT_FEEDS
from app.services.news import fetch_and_ingest


def main() -> None:
    db = SessionLocal()
    try:
        ergebnis = fetch_and_ingest(db, DEFAULT_FEEDS)
        for medienname, anzahl in ergebnis.items():
            zustand = "Abruf fehlgeschlagen" if anzahl < 0 else f"{anzahl} neue Meldung(en)"
            print(f"  {medienname}: {zustand}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
