"""Kennzahlen-Stammdaten: Bundestagswahl-Zweitstimmen je Partei (idempotent).

Öffentliches, stabiles Faktenwissen der Bundeswahlleiterin – jede Zahl trägt
ihre Pflicht-Quelle. Gleiche Methodik für alle Parteien. Veränderliche Zahlen
(Umfragen, Sitze) kommen separat und werden auf dem Server live nachgezogen.

Werte = amtliche Zweitstimmen-Anteile in Prozent. CDU und CSU stehen getrennt
(getrennte Stimmzettel; die CSU tritt nur in Bayern an). Einige Nachkomma-Werte
kleiner Parteien der Wahl 2025 sind als ``vorlaeufig`` markiert und beim Deploy
gegen die amtliche Quelle zu verifizieren.

Aufruf:  python -m scripts.seed_kennzahlen
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import SessionLocal
from app.enums import AuditAktion, Kennzahlart
from app.models import Kennzahl, Partei

QUELLE = "Bundeswahlleiterin"
QUELLE_URL = "https://www.bundeswahlleiterin.de/bundestagswahlen.html"

# (parteiname, prozent, vorlaeufig, bemerkung)
BTW_2021: list[tuple[str, float, bool, str | None]] = [
    ("SPD", 25.7, False, None),
    ("CDU", 18.9, False, None),
    ("Grüne", 14.8, False, None),
    ("FDP", 11.5, False, None),
    ("AfD", 10.3, False, None),
    ("CSU", 5.2, False, None),
    ("Die Linke", 4.9, False, "unter 5 %, Einzug über Grundmandate"),
    ("Freie Wähler", 2.4, False, None),
]

BTW_2025: list[tuple[str, float, bool, str | None]] = [
    ("CDU", 22.6, False, None),
    ("AfD", 20.8, False, None),
    ("SPD", 16.4, False, None),
    ("Grüne", 11.6, False, None),
    ("Die Linke", 8.8, False, None),
    ("CSU", 6.0, False, None),
    ("BSW", 4.97, True, "knapp unter 5 % – Nachkommastelle beim Deploy prüfen"),
    ("FDP", 4.3, False, "unter 5 %, kein Einzug"),
    ("Freie Wähler", 1.6, True, "Nachkommastelle beim Deploy prüfen"),
]

WAHLEN: list[tuple[str, dt.date, list]] = [
    ("Bundestagswahl 2021", dt.date(2021, 9, 26), BTW_2021),
    ("Bundestagswahl 2025", dt.date(2025, 2, 23), BTW_2025),
]


def ensure_kennzahlen(db: Session) -> int:
    """Legt Wahlergebnis-Kennzahlen an bzw. aktualisiert sie (idempotent).

    Eindeutig je (Partei, Art, Zeitpunkt). Rückgabe: Anzahl neu angelegter.
    """
    parteien = {p.name: p for p in db.scalars(select(Partei)).all()}
    art = Kennzahlart.bundestagswahl_zweitstimme
    neu = 0
    for label, datum, ergebnisse in WAHLEN:
        for name, prozent, vorlaeufig, bemerkung in ergebnisse:
            partei = parteien.get(name)
            if partei is None:
                continue  # Partei (noch) nicht angelegt -> überspringen
            vorhanden = db.scalar(
                select(Kennzahl).where(
                    Kennzahl.partei_id == partei.id,
                    Kennzahl.art == art,
                    Kennzahl.zeitpunkt == datum,
                )
            )
            if vorhanden is None:
                k = Kennzahl(
                    partei_id=partei.id, art=art, wert=prozent, einheit="%",
                    zeitpunkt=datum, label=label, quelle_url=QUELLE_URL,
                    quelle_name=QUELLE, vorlaeufig=vorlaeufig, bemerkung=bemerkung,
                )
                db.add(k)
                db.flush()
                audit(db, tabelle="kennzahlen", datensatz_id=k.id,
                      aktion=AuditAktion.erstellt, akteur="seed:kennzahlen")
                neu += 1
            else:
                vorhanden.wert = prozent
                vorhanden.label = label
                vorhanden.quelle_url = QUELLE_URL
                vorhanden.quelle_name = QUELLE
                vorhanden.vorlaeufig = vorlaeufig
                vorhanden.bemerkung = bemerkung
    if neu or db.dirty:
        db.commit()
    return neu


def main() -> None:
    db = SessionLocal()
    try:
        print(f"Kennzahlen (Wahlergebnisse) ergänzt: {ensure_kennzahlen(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
