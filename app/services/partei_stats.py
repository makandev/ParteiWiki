"""Aggregierte Kennzahlen je Partei für Übersicht, Vergleich und Steckbrief.

An einer Stelle gebündelt, damit Vergleichsseite und Partei-Profil dieselbe
Logik nutzen (gleiche Methodik für alle Parteien, keine Doppelpflege).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import Kennzahlart
from app.models import Erwaehnung, Kennzahl, Meldung, Politiker


def wahlergebnisse(db: Session) -> dict[tuple[uuid.UUID, int], float]:
    """Zweitstimmen-Anteile je (Partei, Wahljahr)."""
    ergebnis: dict[tuple[uuid.UUID, int], float] = {}
    for k in db.scalars(
        select(Kennzahl).where(
            Kennzahl.art == Kennzahlart.bundestagswahl_zweitstimme
        )
    ).all():
        ergebnis[(k.partei_id, k.zeitpunkt.year)] = k.wert
    return ergebnis


def aktuelle_umfrage(db: Session) -> dict[uuid.UUID, Kennzahl]:
    """Je Partei die jüngste Umfrage-Kennzahl (falls vorhanden)."""
    neueste: dict[uuid.UUID, Kennzahl] = {}
    for k in db.scalars(
        select(Kennzahl)
        .where(Kennzahl.art == Kennzahlart.umfrage_bund)
        .order_by(Kennzahl.zeitpunkt.desc())
    ).all():
        neueste.setdefault(k.partei_id, k)
    return neueste


def mdb_zahl_je_partei(db: Session) -> dict[uuid.UUID, int]:
    """Anzahl aktiver Abgeordneter (amt enthält 'MdB') je Partei."""
    ergebnis: dict[uuid.UUID, int] = {}
    for p in db.scalars(select(Politiker).where(Politiker.aktiv.is_(True))).all():
        if p.amt and "MdB" in p.amt:
            ergebnis[p.partei_id] = ergebnis.get(p.partei_id, 0) + 1
    return ergebnis


def news_zahl_je_partei(db: Session, *, tage: int = 30) -> dict[uuid.UUID, int]:
    """Anzahl erfasster Meldungen je Partei im Zeitfenster (über Erwähnungen)."""
    seit = dt.datetime.now() - dt.timedelta(days=tage)
    ergebnis: dict[uuid.UUID, int] = {}
    for partei_id, anzahl in db.execute(
        select(Erwaehnung.partei_id, func.count(func.distinct(Meldung.id)))
        .join(Meldung, Meldung.id == Erwaehnung.meldung_id)
        .where(Erwaehnung.partei_id.is_not(None), Meldung.erfasst_am >= seit)
        .group_by(Erwaehnung.partei_id)
    ).all():
        ergebnis[partei_id] = anzahl
    return ergebnis
