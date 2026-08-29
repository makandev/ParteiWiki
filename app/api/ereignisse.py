"""Ereignisse – Kern der App. Enthält die 3-Quellen-Regel-Logik."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.neutralitaet import aktualisiere_status, zaehle_unabhaengige_quellen
from app.database import get_db
from app.enums import AuditAktion, Ereigniskategorie
from app.models import Ereignis, EreignisQuelle, Partei, Quelle
from app.schemas import (
    EreignisCreate,
    EreignisOut,
    EreignisQuelleCreate,
    EreignisQuelleOut,
    SnapshotOut,
)
from app.services.rag import index_ereignis

router = APIRouter(prefix="/ereignisse", tags=["ereignisse"])


def _to_out(db: Session, ereignis: Ereignis) -> EreignisOut:
    out = EreignisOut.model_validate(ereignis)
    out.anzahl_unabhaengige_quellen = zaehle_unabhaengige_quellen(db, ereignis)
    return out


@router.get("", response_model=list[EreignisOut])
def liste_ereignisse(
    db: Session = Depends(get_db),
    partei_id: uuid.UUID | None = None,
    kategorie: Ereigniskategorie | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    stmt = select(Ereignis).order_by(Ereignis.datum_ereignis.desc().nullslast())
    if partei_id:
        stmt = stmt.where(Ereignis.partei_id == partei_id)
    if kategorie:
        stmt = stmt.where(Ereignis.kategorie == kategorie)
    ereignisse = db.scalars(stmt.limit(limit).offset(offset)).all()
    return [_to_out(db, e) for e in ereignisse]


@router.get("/{ereignis_id}", response_model=EreignisOut)
def hole_ereignis(ereignis_id: uuid.UUID, db: Session = Depends(get_db)):
    ereignis = db.get(Ereignis, ereignis_id)
    if ereignis is None:
        raise HTTPException(404, "Ereignis nicht gefunden")
    return _to_out(db, ereignis)


@router.post("", response_model=EreignisOut, status_code=201)
def erstelle_ereignis(daten: EreignisCreate, db: Session = Depends(get_db)):
    if db.get(Partei, daten.partei_id) is None:
        raise HTTPException(422, "Unbekannte partei_id")
    ereignis = Ereignis(**daten.model_dump())
    db.add(ereignis)
    db.flush()
    # Status initial ableiten (amtliche Feststellung -> sofort bestätigt).
    aktualisiere_status(db, ereignis)
    audit(
        db,
        tabelle="ereignisse",
        datensatz_id=ereignis.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    index_ereignis(db, ereignis)
    db.commit()
    db.refresh(ereignis)
    return _to_out(db, ereignis)


@router.post("/{ereignis_id}/quellen", response_model=EreignisOut, status_code=201)
def fuege_quelle_hinzu(
    ereignis_id: uuid.UUID,
    daten: EreignisQuelleCreate,
    db: Session = Depends(get_db),
):
    """Verknüpft eine Quelle mit dem Ereignis und rechnet den Status neu.

    Sobald genügend unabhängige Quellen vorliegen, wechselt der Status
    automatisch von ``vorlaeufig`` zu ``bestaetigt`` (Kriterien Punkt 1).
    """
    ereignis = db.get(Ereignis, ereignis_id)
    if ereignis is None:
        raise HTTPException(404, "Ereignis nicht gefunden")
    if db.get(Quelle, daten.quelle_id) is None:
        raise HTTPException(422, "Unbekannte quelle_id")

    eq = EreignisQuelle(ereignis_id=ereignis_id, **daten.model_dump())
    db.add(eq)
    db.flush()
    audit(
        db,
        tabelle="ereignis_quellen",
        datensatz_id=eq.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    db.refresh(ereignis)
    alt = ereignis.status
    neu = aktualisiere_status(db, ereignis)
    if neu != alt:
        audit(
            db,
            tabelle="ereignisse",
            datensatz_id=ereignis.id,
            aktion=AuditAktion.geaendert,
            akteur="regel:3-quellen",
        )
    index_ereignis(db, ereignis)
    db.commit()
    db.refresh(ereignis)
    return _to_out(db, ereignis)


@router.get("/{ereignis_id}/quellen", response_model=list[EreignisQuelleOut])
def liste_quellen(ereignis_id: uuid.UUID, db: Session = Depends(get_db)):
    ereignis = db.get(Ereignis, ereignis_id)
    if ereignis is None:
        raise HTTPException(404, "Ereignis nicht gefunden")
    return ereignis.ereignis_quellen


@router.get("/{ereignis_id}/snapshots", response_model=list[SnapshotOut])
def liste_snapshots(ereignis_id: uuid.UUID, db: Session = Depends(get_db)):
    ereignis = db.get(Ereignis, ereignis_id)
    if ereignis is None:
        raise HTTPException(404, "Ereignis nicht gefunden")
    snapshots: list = []
    for eq in ereignis.ereignis_quellen:
        snapshots.extend(eq.snapshots)
    snapshots.sort(key=lambda s: s.snapshot_datum, reverse=True)
    return snapshots
