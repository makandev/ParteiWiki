"""Automatischer Umfrage-Abgleich (läuft auf dem Server, wo Netz besteht).

Holt die jüngste Sonntagsfrage (DAWUM) und legt je Partei eine aktuelle
Umfrage-Kennzahl an – quellenpflichtig, gleiche Methodik für alle. Es wird nur
der aktuelle Stand gehalten (je Partei genau eine Umfrage-Kennzahl); ältere
Umfrage-Werte werden ersetzt. Ohne Netz (Egress-Policy) scheitert der Abruf
sauber und stört die App nicht.
"""
from __future__ import annotations

import datetime as dt

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.enums import Kennzahlart
from app.models import Kennzahl, Partei
from app.services.dawum import DawumClient, UmfrageRoh

QUELLE_URL = "https://dawum.de/Bundestag/"


def import_umfrage(db: Session, roh: UmfrageRoh) -> dict:
    """Ersetzt die aktuelle Umfrage-Kennzahl je Partei durch die neue Erhebung."""
    if not roh.ergebnisse or not roh.datum:
        return {"_status": "keine Umfragedaten"}
    try:
        datum = dt.date.fromisoformat(roh.datum)
    except ValueError:
        return {"_status": f"ungültiges Datum: {roh.datum}"}

    parteien = {p.name: p for p in db.scalars(select(Partei)).all()}
    quelle_name = f"DAWUM / {roh.institut}" if roh.institut else "DAWUM"
    label = f"Umfrage {roh.institut}".strip() if roh.institut else "Umfrage"
    neu = 0
    for name, prozent in roh.ergebnisse.items():
        partei = parteien.get(name)
        if partei is None:
            continue
        # Nur aktuellen Stand halten: vorhandene Umfrage-Werte der Partei ersetzen.
        db.execute(
            delete(Kennzahl).where(
                Kennzahl.partei_id == partei.id,
                Kennzahl.art == Kennzahlart.umfrage_bund,
            )
        )
        bemerkung = "Unionswert (CDU/CSU gemeinsam)" if (
            roh.union_hinweis and name == "CDU"
        ) else None
        db.add(Kennzahl(
            partei_id=partei.id, art=Kennzahlart.umfrage_bund, wert=prozent,
            einheit="%", zeitpunkt=datum, label=label, quelle_url=QUELLE_URL,
            quelle_name=quelle_name, vorlaeufig=False, bemerkung=bemerkung,
        ))
        neu += 1
    db.commit()
    return {"_status": "ok", "parteien": neu, "datum": roh.datum, "institut": roh.institut}


def sync_umfragen(db: Session, *, client: DawumClient | None = None) -> dict:
    """Holt die jüngste Sonntagsfrage und importiert sie. Wirft bei Netzfehlern."""
    eigener = client is None
    client = client or DawumClient()
    try:
        roh = client.neueste_umfrage(parlament="Bundestag")
    finally:
        if eigener:
            client.close()
    if roh is None:
        return {"_status": "keine Umfrage gefunden"}
    return import_umfrage(db, roh)


def sync_umfragen_still(db: Session) -> dict | None:
    """Wie ``sync_umfragen``, fängt Netzfehler ab (für den Start-Job)."""
    try:
        return sync_umfragen(db)
    except httpx.HTTPError as exc:  # pragma: no cover - netzabhängig
        print(f"[umfrage-sync] Abruf nicht möglich (Netz/Egress?): {exc}")
        return None
