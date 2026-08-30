"""Snapshot-Endpunkte inkl. manueller Prüfung (Vier-Augen-Prinzip).

Redaktionelle Kriterien 4b/4c: Automatisch erkannte Änderungen bleiben
zunächst "möglicherweise verändert". Erst nach manueller Prüfung setzt ein
Mensch den Status auf "bestätigt verändert" / "entfernt" – oder verwirft den
Fehlalarm ("original"). Die Prüfung wird mit Name/Zeit und im Audit-Log
dokumentiert.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import get_db
from app.enums import AuditAktion, SnapshotStatus
from app.models import ArtikelSnapshot
from app.schemas import SnapshotOut

router = APIRouter(prefix="/snapshots", tags=["diff-tracking"])

# Zulässige Ergebnisse einer manuellen Prüfung.
PRUEFBARE_ZIELE = {
    SnapshotStatus.bestaetigt_veraendert,
    SnapshotStatus.entfernt,
    SnapshotStatus.original,  # Fehlalarm verworfen
}


class SnapshotPruefung(BaseModel):
    status: SnapshotStatus
    geprueft_von: str


@router.get("/offen", response_model=list[SnapshotOut])
def offene_pruefungen(db: Session = Depends(get_db)):
    """Snapshots, die auf manuelle Prüfung warten."""
    return db.scalars(
        select(ArtikelSnapshot)
        .where(ArtikelSnapshot.status == SnapshotStatus.moeglicherweise_veraendert)
        .order_by(ArtikelSnapshot.snapshot_datum.desc())
    ).all()


@router.post("/{snapshot_id}/pruefen", response_model=SnapshotOut)
def pruefe_snapshot(
    snapshot_id: uuid.UUID,
    daten: SnapshotPruefung,
    db: Session = Depends(get_db),
):
    snapshot = db.get(ArtikelSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "Snapshot nicht gefunden")
    if daten.status not in PRUEFBARE_ZIELE:
        raise HTTPException(
            422,
            "Prüfung darf nur auf 'bestaetigt_veraendert', 'entfernt' oder "
            "'original' (Fehlalarm) setzen.",
        )
    snapshot.status = daten.status
    snapshot.geprueft_von = f"{daten.geprueft_von} ({dt.date.today().isoformat()})"
    audit(
        db,
        tabelle="artikel_snapshots",
        datensatz_id=snapshot.id,
        aktion=AuditAktion.geaendert,
        akteur=f"pruefung:{daten.geprueft_von}",
    )
    db.commit()
    db.refresh(snapshot)
    return snapshot
