"""Server-gerenderte Web-Ansichten (Jinja2): Profil & Timeline für den Pilot."""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.neutralitaet import zaehle_unabhaengige_quellen
from app.database import get_db
from app.enums import Vertrauensstufe
from app.models import Ereignis, Meldung, MethodikChangelog, Partei, Quelle
from app.services import rag
from app.web.labels import KATEGORIE_LABEL, SNAPSHOT_LABEL, STATUS_LABEL

router = APIRouter(tags=["web"], include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

templates.env.globals.update(
    kategorie_label=KATEGORIE_LABEL,
    status_label=STATUS_LABEL,
    snapshot_label=SNAPSHOT_LABEL,
    jetzt=lambda: dt.datetime.now(),
)


@router.get("/", response_class=HTMLResponse)
def startseite(request: Request, db: Session = Depends(get_db)):
    parteien = db.scalars(select(Partei).order_by(Partei.name)).all()
    changelog = db.scalars(
        select(MethodikChangelog).order_by(MethodikChangelog.datum.desc()).limit(5)
    ).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "parteien": parteien, "changelog": changelog},
    )


@router.get("/parteien/{partei_id}", response_class=HTMLResponse)
def partei_profil(
    partei_id: uuid.UUID, request: Request, db: Session = Depends(get_db)
):
    partei = db.get(Partei, partei_id)
    if partei is None:
        raise HTTPException(404, "Partei nicht gefunden")
    ereignisse = db.scalars(
        select(Ereignis)
        .where(Ereignis.partei_id == partei_id)
        .order_by(Ereignis.datum_ereignis.desc().nullslast())
    ).all()
    quellen_je_ereignis = {
        e.id: zaehle_unabhaengige_quellen(db, e) for e in ereignisse
    }
    positionen = sorted(
        partei.positionen, key=lambda p: p.geaendert_am or dt.date.min, reverse=True
    )
    # Nachrichten über die Partei (automatisch aggregiert – zum Lesen).
    meldungen = db.scalars(
        select(Meldung)
        .where(Meldung.partei_id == partei_id)
        .order_by(Meldung.erfasst_am.desc())
        .limit(30)
    ).all()
    mediennamen = {q.id: q.medienname for q in db.scalars(select(Quelle)).all()}
    # Stark beachtete Themen (mehrere unabhängige Quellen) – neutral hervorgehoben.
    from app.api.news import framing_cluster

    viel_beachtet = framing_cluster(db=db, partei_id=partei_id, limit=6)
    return templates.TemplateResponse(
        "partei.html",
        {
            "request": request,
            "partei": partei,
            "politiker": sorted(partei.politiker, key=lambda p: p.name),
            "positionen": positionen,
            "ereignisse": ereignisse,
            "quellen_je_ereignis": quellen_je_ereignis,
            "meldungen": meldungen,
            "mediennamen": mediennamen,
            "viel_beachtet": viel_beachtet,
        },
    )


@router.get("/ereignisse/{ereignis_id}", response_class=HTMLResponse)
def ereignis_detail(
    ereignis_id: uuid.UUID, request: Request, db: Session = Depends(get_db)
):
    ereignis = db.get(Ereignis, ereignis_id)
    if ereignis is None:
        raise HTTPException(404, "Ereignis nicht gefunden")
    snapshots = []
    for eq in ereignis.ereignis_quellen:
        snapshots.extend(eq.snapshots)
    snapshots.sort(key=lambda s: s.snapshot_datum, reverse=True)
    return templates.TemplateResponse(
        "ereignis.html",
        {
            "request": request,
            "ereignis": ereignis,
            "anzahl_quellen": zaehle_unabhaengige_quellen(db, ereignis),
            "snapshots": snapshots,
        },
    )


@router.get("/news", response_class=HTMLResponse)
def news_seite(request: Request, db: Session = Depends(get_db)):
    from app.api.news import framing_cluster

    meldungen = db.scalars(
        select(Meldung).order_by(Meldung.erfasst_am.desc()).limit(50)
    ).all()
    cluster = framing_cluster(db=db, partei_id=None, limit=20)
    mediennamen = {q.id: q.medienname for q in db.scalars(select(Quelle)).all()}
    parteinamen = {p.id: p.name for p in db.scalars(select(Partei)).all()}
    return templates.TemplateResponse(
        "news.html",
        {
            "request": request,
            "meldungen": meldungen,
            "cluster": cluster,
            "mediennamen": mediennamen,
            "parteinamen": parteinamen,
        },
    )


@router.get("/quellen/ausschlussliste", response_class=HTMLResponse)
def ausschlussliste(request: Request, db: Session = Depends(get_db)):
    quellen = db.scalars(
        select(Quelle)
        .where(Quelle.vertrauensstufe == Vertrauensstufe.ausgeschlossen)
        .order_by(Quelle.medienname)
    ).all()
    return templates.TemplateResponse(
        "ausschlussliste.html", {"request": request, "quellen": quellen}
    )


@router.get("/fragen", response_class=HTMLResponse)
@router.post("/fragen", response_class=HTMLResponse)
def fragen_seite(
    request: Request, frage: str = Form(default=""), db: Session = Depends(get_db)
):
    antwort = None
    antwort_text = ""
    if frage.strip():
        antwort = rag.frage_stellen(db, frage.strip())
        antwort_text = rag.formuliere_antwort(antwort)
    return templates.TemplateResponse(
        "fragen.html",
        {"request": request, "frage": frage, "antwort": antwort, "antwort_text": antwort_text},
    )
