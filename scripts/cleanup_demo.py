"""Entfernt frühere Demonstrations-Daten (idempotent).

Der alte Seed legte Beispiel-Ereignisse/-Positionen/-Abstimmungen an, klar als
Demonstrationsdaten markiert. Diese Funktion löscht genau solche Datensätze –
nichts anderes. Sie wird beim Deploy automatisch ausgeführt (Entrypoint) und
kann auch manuell laufen:  python -m scripts.cleanup_demo
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Abstimmung, Ereignis, PositionsHistorie


def bereinige_demo(db: Session) -> dict[str, int]:
    """Löscht Demo-markierte Ereignisse/Positionen/Abstimmungen. Rückgabe: Zähler."""
    ereignisse = db.scalars(
        select(Ereignis).where(
            or_(
                Ereignis.titel.ilike("%Demonstrationsdaten%"),
                Ereignis.beschreibung.ilike("%Demonstrationsdaten%"),
                Ereignis.beschreibung.ilike("%Seed-Beispiel%"),
            )
        )
    ).all()
    positionen = db.scalars(
        select(PositionsHistorie).where(
            PositionsHistorie.thema.ilike("%Demonstrationsdaten%")
        )
    ).all()
    abstimmungen = db.scalars(
        select(Abstimmung).where(Abstimmung.thema.ilike("Beispiel-%"))
    ).all()

    for obj in (*ereignisse, *positionen, *abstimmungen):
        db.delete(obj)  # DB-seitige ON DELETE CASCADE räumt Quellen/Snapshots/Embeddings
    db.commit()
    return {
        "ereignisse": len(ereignisse),
        "positionen": len(positionen),
        "abstimmungen": len(abstimmungen),
    }


def main() -> None:
    db = SessionLocal()
    try:
        print("Demo-Bereinigung:", bereinige_demo(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
