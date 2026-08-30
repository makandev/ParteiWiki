"""Politiker-Endpunkte."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import get_db
from app.enums import AuditAktion
from app.models import Partei, Politiker
from app.schemas import AbstimmungOut, PolitikerCreate, PolitikerOut

router = APIRouter(prefix="/politiker", tags=["politiker"])


@router.get("", response_model=list[PolitikerOut])
def liste_politiker(
    db: Session = Depends(get_db), partei_id: uuid.UUID | None = None
):
    stmt = select(Politiker).order_by(Politiker.name)
    if partei_id:
        stmt = stmt.where(Politiker.partei_id == partei_id)
    return db.scalars(stmt).all()


@router.get("/{politiker_id}", response_model=PolitikerOut)
def hole_politiker(politiker_id: uuid.UUID, db: Session = Depends(get_db)):
    politiker = db.get(Politiker, politiker_id)
    if politiker is None:
        raise HTTPException(404, "Politiker nicht gefunden")
    return politiker


@router.post("", response_model=PolitikerOut, status_code=201)
def erstelle_politiker(daten: PolitikerCreate, db: Session = Depends(get_db)):
    if db.get(Partei, daten.partei_id) is None:
        raise HTTPException(422, "Unbekannte partei_id")
    politiker = Politiker(**daten.model_dump())
    db.add(politiker)
    db.flush()
    audit(
        db,
        tabelle="politiker",
        datensatz_id=politiker.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    db.commit()
    db.refresh(politiker)
    return politiker


@router.get("/{politiker_id}/abstimmungen", response_model=list[AbstimmungOut])
def abstimmungen_des_politikers(
    politiker_id: uuid.UUID, db: Session = Depends(get_db)
):
    politiker = db.get(Politiker, politiker_id)
    if politiker is None:
        raise HTTPException(404, "Politiker nicht gefunden")
    return politiker.abstimmungen
