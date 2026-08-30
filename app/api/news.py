"""Nachrichten-Endpunkte inkl. Framing-Vergleich (Cluster)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meldung, Quelle
from app.schemas import ClusterMeldung, ClusterOut, MeldungOut

router = APIRouter(prefix="/meldungen", tags=["news"])


@router.get("", response_model=list[MeldungOut])
def liste_meldungen(
    db: Session = Depends(get_db),
    partei_id: uuid.UUID | None = None,
    cluster_id: uuid.UUID | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    stmt = select(Meldung).order_by(Meldung.erfasst_am.desc())
    if partei_id:
        stmt = stmt.where(Meldung.partei_id == partei_id)
    if cluster_id:
        stmt = stmt.where(Meldung.cluster_id == cluster_id)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/cluster", response_model=list[ClusterOut])
def framing_cluster(
    db: Session = Depends(get_db),
    partei_id: uuid.UUID | None = None,
    limit: int = Query(20, le=100),
):
    """Cluster mit mindestens zwei unabhängigen Quellen (Framing-Vergleich)."""
    unter = (
        select(
            Meldung.cluster_id.label("cid"),
            func.count(func.distinct(Meldung.quelle_id)).label("n"),
        )
        .where(Meldung.cluster_id.is_not(None))
    )
    if partei_id:
        unter = unter.where(Meldung.partei_id == partei_id)
    unter = unter.group_by(Meldung.cluster_id).having(
        func.count(func.distinct(Meldung.quelle_id)) >= 2
    ).limit(limit)

    ergebnis: list[ClusterOut] = []
    for cid, n in db.execute(unter).all():
        meldungen = db.execute(
            select(Meldung, Quelle.medienname)
            .join(Quelle, Meldung.quelle_id == Quelle.id)
            .where(Meldung.cluster_id == cid)
            .order_by(Meldung.veroeffentlicht_am.desc().nullslast())
        ).all()
        ergebnis.append(ClusterOut(
            cluster_id=cid,
            anzahl_quellen=n,
            meldungen=[
                ClusterMeldung(
                    id=m.id, medienname=name, titel=m.titel, url=m.url,
                    veroeffentlicht_am=m.veroeffentlicht_am,
                )
                for m, name in meldungen
            ],
        ))
    return ergebnis


@router.get("/{meldung_id}", response_model=MeldungOut)
def hole_meldung(meldung_id: uuid.UUID, db: Session = Depends(get_db)):
    meldung = db.get(Meldung, meldung_id)
    if meldung is None:
        raise HTTPException(404, "Meldung nicht gefunden")
    return meldung
