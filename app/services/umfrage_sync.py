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

from app.core.audit import audit
from app.enums import AuditAktion, Kennzahlart
from app.models import Kennzahl, Partei
from app.services.dawum import DawumClient, UmfrageRoh

QUELLE_URL = "https://dawum.de/Bundestag/"


def import_umfrage(db: Session, roh: UmfrageRoh) -> dict:
    """Ersetzt den aktuellen Umfrage-Stand durch die neue Erhebung.

    Eine Sonntagsfrage ist ein konsistenter Snapshot (ein Institut, ein Datum).
    Deshalb wird der komplette bisherige Umfrage-Stand einmalig entfernt und neu
    gesetzt – so bleiben keine veralteten Werte einzelner Parteien zurück."""
    if not roh.ergebnisse or not roh.datum:
        return {"_status": "keine Umfragedaten"}
    try:
        datum = dt.date.fromisoformat(roh.datum)
    except ValueError:
        return {"_status": f"ungültiges Datum: {roh.datum}"}

    parteien = {p.name: p for p in db.scalars(select(Partei)).all()}
    quelle_name = f"DAWUM / {roh.institut}" if roh.institut else "DAWUM"
    label = f"Umfrage {roh.institut}".strip() if roh.institut else "Umfrage"

    # Kompletten bisherigen Umfrage-Stand ersetzen (kein Rest veralteter Werte).
    db.execute(delete(Kennzahl).where(Kennzahl.art == Kennzahlart.umfrage_bund))

    neu = 0
    for name, prozent in roh.ergebnisse.items():
        partei = parteien.get(name)
        if partei is None:
            continue
        bemerkung = "Unionswert (CDU/CSU gemeinsam)" if (
            roh.union_hinweis and name == "CDU"
        ) else None
        k = Kennzahl(
            partei_id=partei.id, art=Kennzahlart.umfrage_bund, wert=prozent,
            einheit="%", zeitpunkt=datum, label=label, quelle_url=QUELLE_URL,
            quelle_name=quelle_name, vorlaeufig=False, bemerkung=bemerkung,
        )
        db.add(k)
        db.flush()
        audit(db, tabelle="kennzahlen", datensatz_id=k.id,
              aktion=AuditAktion.erstellt, akteur="umfrage-sync:dawum")
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
