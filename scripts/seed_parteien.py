"""Stammdaten aller relevanten Parteien (idempotent).

Legt fehlende Parteien an, damit die Übersicht alle zeigt. Bewusst nur
neutrale, gut belegte Basisfakten (Name, Gründungsjahr, offizielles Programm);
veränderliche Zahlen (Wahlergebnisse, Umfragen, Sitze) kommen separat als
belegte Kennzahlen dazu.

Aufruf:  python -m scripts.seed_parteien
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Partei

# (name, gruendungsjahr, programm_url, kurzbeschreibung)
PARTEIEN: list[tuple[str, int, str, str]] = [
    ("CDU", 1945, "https://www.cdu.de/", "Christlich Demokratische Union Deutschlands."),
    ("CSU", 1945, "https://www.csu.de/", "Christlich-Soziale Union in Bayern."),
    ("SPD", 1863, "https://www.spd.de/", "Sozialdemokratische Partei Deutschlands."),
    ("Grüne", 1980, "https://www.gruene.de/", "Bündnis 90/Die Grünen."),
    ("FDP", 1948, "https://www.fdp.de/", "Freie Demokratische Partei."),
    ("AfD", 2013, "https://www.afd.de/grundsatzprogramm/", "Alternative für Deutschland."),
    ("Die Linke", 2007, "https://www.die-linke.de/", "Partei Die Linke."),
    ("BSW", 2024, "https://bsw-vg.de/", "Bündnis Sahra Wagenknecht."),
    ("Freie Wähler", 2009, "https://www.freiewaehler.eu/", "FREIE WÄHLER (Bundesvereinigung)."),
]


def ensure_parteien(db: Session) -> int:
    """Legt fehlende Parteien an. Rückgabe: Anzahl neu angelegter."""
    vorhanden = {p.name for p in db.scalars(select(Partei)).all()}
    neu = 0
    for name, jahr, url, kurz in PARTEIEN:
        if name in vorhanden:
            continue
        db.add(Partei(
            name=name, gruendungsjahr=jahr, programm_url=url,
            kurzbeschreibung=kurz, letzte_aktualisierung=dt.date.today(),
        ))
        neu += 1
    if neu:
        db.commit()
    return neu


def main() -> None:
    db = SessionLocal()
    try:
        print(f"Parteien ergänzt: {ensure_parteien(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
