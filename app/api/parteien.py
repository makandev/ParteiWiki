"""Parteien-Endpunkte inkl. zugehöriger Politiker, Positionen, Ereignisse."""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import get_db
from app.enums import AuditAktion
from app.models import Ereignis, Partei
from app.schemas import (
    EreignisOut,
    ParteiCreate,
    ParteiOut,
    PolitikerOut,
    PositionsHistorieOut,
)

router = APIRouter(prefix="/parteien", tags=["parteien"])


@router.get("", response_model=list[ParteiOut])
def liste_parteien(db: Session = Depends(get_db)):
    return db.scalars(select(Partei).order_by(Partei.name)).all()


@router.get("/{partei_id}", response_model=ParteiOut)
def hole_partei(partei_id: uuid.UUID, db: Session = Depends(get_db)):
    partei = db.get(Partei, partei_id)
    if partei is None:
        raise HTTPException(404, "Partei nicht gefunden")
    return partei


@router.post("", response_model=ParteiOut, status_code=201)
def erstelle_partei(daten: ParteiCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Partei).where(Partei.name == daten.name)):
        raise HTTPException(409, "Partei mit diesem Namen existiert bereits")
    partei = Partei(**daten.model_dump())
    partei.letzte_aktualisierung = partei.letzte_aktualisierung or dt.date.today()
    db.add(partei)
    db.flush()
    audit(
        db,
        tabelle="parteien",
        datensatz_id=partei.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    db.commit()
    db.refresh(partei)
    return partei


@router.get("/{partei_id}/politiker", response_model=list[PolitikerOut])
def politiker_der_partei(partei_id: uuid.UUID, db: Session = Depends(get_db)):
    partei = db.get(Partei, partei_id)
    if partei is None:
        raise HTTPException(404, "Partei nicht gefunden")
    return partei.politiker


@router.get("/{partei_id}/positionen", response_model=list[PositionsHistorieOut])
def positionen_der_partei(partei_id: uuid.UUID, db: Session = Depends(get_db)):
    partei = db.get(Partei, partei_id)
    if partei is None:
        raise HTTPException(404, "Partei nicht gefunden")
    return sorted(
        partei.positionen,
        key=lambda p: p.geaendert_am or dt.date.min,
        reverse=True,
    )


@router.get("/{partei_id}/ereignisse", response_model=list[EreignisOut])
def ereignisse_der_partei(partei_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.api.ereignisse import _to_out

    partei = db.get(Partei, partei_id)
    if partei is None:
        raise HTTPException(404, "Partei nicht gefunden")
    ereignisse = db.scalars(
        select(Ereignis)
        .where(Ereignis.partei_id == partei_id)
        .order_by(Ereignis.datum_ereignis.desc().nullslast())
    ).all()
    return [_to_out(db, e) for e in ereignisse]
