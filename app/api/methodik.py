"""Methodik-Changelog – Transparenz-Pflicht (Kriterien Punkt 6).

Jede Änderung an der Methodik/den Kriterien wird öffentlich dokumentiert
(Datum, was geändert, warum).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MethodikChangelog
from app.schemas import MethodikChangelogCreate, MethodikChangelogOut

router = APIRouter(prefix="/methodik", tags=["methodik"])


@router.get("/changelog", response_model=list[MethodikChangelogOut])
def changelog(db: Session = Depends(get_db)):
    return db.scalars(
        select(MethodikChangelog).order_by(MethodikChangelog.datum.desc())
    ).all()


@router.post("/changelog", response_model=MethodikChangelogOut, status_code=201)
def eintrag_hinzufuegen(
    daten: MethodikChangelogCreate, db: Session = Depends(get_db)
):
    eintrag = MethodikChangelog(**daten.model_dump())
    db.add(eintrag)
    db.commit()
    db.refresh(eintrag)
    return eintrag
