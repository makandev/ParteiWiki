"""Quellen-Endpunkte inkl. öffentlich einsehbarer Ausschlussliste (Kriterien 4d)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.database import get_db
from app.enums import AuditAktion, Vertrauensstufe
from app.models import Quelle
from app.schemas import QuelleCreate, QuelleOut

router = APIRouter(prefix="/quellen", tags=["quellen"])


@router.get("", response_model=list[QuelleOut])
def liste_quellen(
    db: Session = Depends(get_db),
    vertrauensstufe: Vertrauensstufe | None = None,
):
    stmt = select(Quelle).order_by(Quelle.medienname)
    if vertrauensstufe:
        stmt = stmt.where(Quelle.vertrauensstufe == vertrauensstufe)
    return db.scalars(stmt).all()


@router.get("/ausschlussliste", response_model=list[QuelleOut])
def ausschlussliste(db: Session = Depends(get_db)):
    """Öffentlich einsehbare Liste ausgeschlossener Quellen (Kriterien 4d)."""
    return db.scalars(
        select(Quelle)
        .where(Quelle.vertrauensstufe == Vertrauensstufe.ausgeschlossen)
        .order_by(Quelle.medienname)
    ).all()


@router.post("", response_model=QuelleOut, status_code=201)
def erstelle_quelle(daten: QuelleCreate, db: Session = Depends(get_db)):
    quelle = Quelle(**daten.model_dump())
    db.add(quelle)
    db.flush()
    audit(
        db,
        tabelle="quellen",
        datensatz_id=quelle.id,
        aktion=AuditAktion.erstellt,
        akteur="api",
    )
    db.commit()
    db.refresh(quelle)
    return quelle
