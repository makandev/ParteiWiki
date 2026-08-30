"""Schlanker Seed für den Pilot (Partei: AfD) – nur echte Stammdaten.

Bewusst OHNE erfundene Ereignisse/Positionen: Inhalte entstehen aus der
Ingestion (Nachrichten, Politiker, Abstimmungen) und – wo redaktionell nötig –
aus geprüften Quellen. Gleiche Methodik gilt für jede Partei.

Aufruf:  python -m scripts.seed
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.database import SessionLocal
from app.enums import Vertrauensstufe
from app.models import MethodikChangelog, Partei, Politiker, Quelle


def _quelle(db, medienname, url_basis, stufe=Vertrauensstufe.serioes, begruendung=None) -> int:
    if db.scalar(select(Quelle).where(Quelle.medienname == medienname)) is not None:
        return 0
    db.add(Quelle(medienname=medienname, url_basis=url_basis,
                  vertrauensstufe=stufe, ausschluss_begruendung=begruendung))
    return 1


def ensure_quellen(db) -> int:
    """Legt fehlende Quellen an (kuratierte Feeds + Ausschlussliste). Idempotent."""
    from app.feeds import AUSGESCHLOSSENE, DEFAULT_FEEDS
    neu = 0
    for feed in DEFAULT_FEEDS:
        neu += _quelle(db, feed.medienname, feed.url_basis, feed.vertrauensstufe)
    for name, basis, grund in AUSGESCHLOSSENE:
        neu += _quelle(db, name, basis, Vertrauensstufe.ausgeschlossen, grund)
    if neu:
        db.commit()
    return neu


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(Partei).where(Partei.name == "AfD")):
            print("AfD bereits vorhanden – Seed übersprungen.")
            return

        partei = Partei(
            name="AfD",
            kurzbeschreibung=(
                "Deutsche politische Partei, gegründet 2013; seit 2017 im "
                "Deutschen Bundestag vertreten."
            ),
            gruendungsjahr=2013,
            programm_url="https://www.afd.de/grundsatzprogramm/",
            letzte_aktualisierung=dt.date.today(),
        )
        db.add(partei)
        db.flush()

        # Reale Co-Vorsitzende als Startpunkt; weitere kommen aus abgeordnetenwatch.
        db.add_all([
            Politiker(partei_id=partei.id, name="Alice Weidel",
                      amt="Bundessprecherin (Co-Vorsitz), MdB"),
            Politiker(partei_id=partei.id, name="Tino Chrupalla",
                      amt="Bundessprecher (Co-Vorsitz), MdB"),
        ])

        ensure_quellen(db)  # kuratierte Feeds + öffentliche Ausschlussliste

        db.add(MethodikChangelog(
            was_geaendert="Initiale Stammdaten (Pilot AfD) und Quellenliste angelegt.",
            warum=("Inhalte entstehen aus der Ingestion und geprüften Quellen; "
                   "keine erfundenen Ereignisse. Gleiche Methodik für jede Partei."),
        ))

        db.commit()

        # Alle weiteren Parteien ergänzen (Übersicht zeigt alle).
        from scripts.seed_parteien import ensure_parteien
        ensure_parteien(db)
        print("Seed abgeschlossen: Parteien-Stammdaten, AfD-Politiker, Quellenliste.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
