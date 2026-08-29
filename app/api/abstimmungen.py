"""Abstimmungs-Endpunkte (Bundestag Open Data)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import get_db
from app.enums import AuditAktion
from app.models import Abstimmung, Politiker
from app.schemas import AbstimmungCreate, AbstimmungOut

router = APIRouter(prefix="/abstimmungen", tags=["abstimmungen"])


@router.post("", response_model=AbstimmungOut, status_code=201)
def erstelle_abstimmung(daten: AbstimmungCreate, db: Session = Depends(get_db)):
    if db.get(Politiker, daten.politiker_id) is None:
        raise HTTPException(422, "Unbekannte politiker_id")
    abstimmung = Abstimmung(**daten.model_dump())
    db.add(abstimmung)
    db.flush()
    audit(
        db,
        tabelle="abstimmungen",
        datensatz_id=abstimmung.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    db.commit()
    db.refresh(abstimmung)
    return abstimmung
