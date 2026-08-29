"""Positions-Historie – Programm-Änderungen über Zeit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import get_db
from app.enums import AuditAktion
from app.models import Partei, PositionsHistorie
from app.schemas import PositionsHistorieCreate, PositionsHistorieOut

router = APIRouter(prefix="/positionen", tags=["positionen"])


@router.post("", response_model=PositionsHistorieOut, status_code=201)
def erstelle_position(
    daten: PositionsHistorieCreate, db: Session = Depends(get_db)
):
    if db.get(Partei, daten.partei_id) is None:
        raise HTTPException(422, "Unbekannte partei_id")
    position = PositionsHistorie(**daten.model_dump())
    db.add(position)
    db.flush()
    audit(
        db,
        tabelle="positions_historie",
        datensatz_id=position.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    db.commit()
    db.refresh(position)
    return position
