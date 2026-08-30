"""Automatischer MdB-Abgleich (läuft auf dem Server, wo Netzzugriff besteht).

Ermittelt die aktuelle Bundestags-Legislaturperiode selbst, holt alle Mandate
und ordnet sie den Parteien zu (idempotent). Gedacht für den einmaligen Lauf
beim App-Start bzw. als Job – in Umgebungen ohne Netzzugang (Egress-Policy)
schlägt der Abruf fehl und wird sauber geloggt, ohne die App zu stören.
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.services.abgeordnetenwatch import AbgeordnetenwatchClient, import_mdb


def sync_mdb(db: Session, *, client: AbgeordnetenwatchClient | None = None) -> dict:
    """Holt und importiert die aktuellen Bundestags-MdBs. Rückgabe: Ergebnis-Dict.

    Wirft ``httpx.HTTPError`` bei Netz-/Egress-Problemen weiter – der Aufrufer
    entscheidet, ob das (z. B. beim Start) still geloggt wird.
    """
    eigener_client = client is None
    client = client or AbgeordnetenwatchClient()
    try:
        periode = client.aktuelle_bundestag_periode()
        if periode is None or periode.externe_id is None:
            return {"_status": "keine Bundestags-Periode gefunden"}
        mandate = client.mandate(parliament_period=periode.externe_id)
    finally:
        if eigener_client:
            client.close()
    ergebnis = import_mdb(db, mandate)
    db.commit()
    ergebnis["_periode"] = periode.label or str(periode.externe_id)
    ergebnis["_mandate_gesamt"] = len(mandate)
    return ergebnis


def sync_mdb_still(db: Session) -> dict | None:
    """Wie ``sync_mdb``, fängt Netzfehler ab (für den Start-Job). None bei Fehler."""
    try:
        return sync_mdb(db)
    except httpx.HTTPError as exc:  # pragma: no cover - netzabhängig
        print(f"[mdb-sync] Abruf nicht möglich (Netz/Egress?): {exc}")
        return None
