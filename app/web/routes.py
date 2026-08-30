"""Server-gerenderte Web-Ansichten (Jinja2): Profil & Timeline für den Pilot."""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ner import PARTEI_ALIASE
from app.core.neutralitaet import zaehle_unabhaengige_quellen
from app.database import get_db
from app.enums import Vertrauensstufe
from app.models import Ereignis, Erwaehnung, Meldung, MethodikChangelog, Partei, Quelle
from app.services import rag
from app.web.labels import (
    KATEGORIE_LABEL,
    SNAPSHOT_LABEL,
    SPEKTRUM_LABEL,
    STATUS_LABEL,
    VERTRAUEN_LABEL,
)

router = APIRouter(tags=["web"], include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

templates.env.globals.update(
    kategorie_label=KATEGORIE_LABEL,
    status_label=STATUS_LABEL,
    snapshot_label=SNAPSHOT_LABEL,
    spektrum_label=SPEKTRUM_LABEL,
    vertrauen_label=VERTRAUEN_LABEL,
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
    partei_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    ohne: str = Query("", description="Medien ausblenden (kommagetrennt)"),
    sort: str = Query("datum", description="datum | medium"),
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
    _quellen = db.scalars(select(Quelle)).all()
    mediennamen = {q.id: q.medienname for q in _quellen}
    medien = {q.id: q for q in _quellen}  # für Orientierungs-Hinweis je Meldung

    # Nachrichten ÜBER die Partei: nur Meldungen, in denen die Partei (per NER)
    # erwähnt wird UND im Titel vorkommt. Das verhindert Fremd-Themen (z. B. eine
    # Trump-Meldung, in der die Partei nur am Rande genannt wird) und ordnet
    # Meldungen dank Erwähnungen der richtigen Partei zu (auch mehreren).
    namen = [partei.name, *PARTEI_ALIASE.get(partei.name, [])]
    kandidaten = db.scalars(
        select(Meldung)
        .join(Erwaehnung, Erwaehnung.meldung_id == Meldung.id)
        .where(Erwaehnung.partei_id == partei_id)
        .order_by(Meldung.erfasst_am.desc())
        .distinct()
        .limit(120)
    ).all()

    def im_titel(m):
        titel = (m.titel or "").lower()
        return any(n.lower() in titel for n in namen)

    ausgeblendet = {m.strip() for m in ohne.split(",") if m.strip()}
    meldungen = [
        m for m in kandidaten
        if im_titel(m) and mediennamen.get(m.quelle_id) not in ausgeblendet
    ]
    if sort == "medium":
        meldungen.sort(key=lambda m: (mediennamen.get(m.quelle_id, ""), m.erfasst_am))
    meldungen = meldungen[:40]

    verfuegbare_medien = sorted({
        mediennamen.get(m.quelle_id) for m in kandidaten
        if im_titel(m) and mediennamen.get(m.quelle_id)
    })

    # Viel beachtet: Cluster unter diesen Meldungen mit >= 2 unabhängigen Quellen.
    from collections import defaultdict

    cluster_map: dict = defaultdict(list)
    for m in meldungen:
        if m.cluster_id:
            cluster_map[m.cluster_id].append(m)
    viel_beachtet = []
    for cid, ms in cluster_map.items():
        quellen = {m.quelle_id for m in ms}
        if len(quellen) >= 2:
            viel_beachtet.append({
                "anzahl_quellen": len(quellen),
                "meldungen": [
                    {"medienname": mediennamen.get(m.quelle_id, "Quelle"),
                     "titel": m.titel, "url": m.url}
                    for m in ms
                ],
            })
    viel_beachtet.sort(key=lambda c: c["anzahl_quellen"], reverse=True)

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
            "medien": medien,
            "viel_beachtet": viel_beachtet[:6],
            "verfuegbare_medien": verfuegbare_medien,
            "ausgeblendet": ausgeblendet,
            "sort": sort,
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
    _quellen = db.scalars(select(Quelle)).all()
    mediennamen = {q.id: q.medienname for q in _quellen}
    medien = {q.id: q for q in _quellen}
    parteinamen = {p.id: p.name for p in db.scalars(select(Partei)).all()}
    return templates.TemplateResponse(
        "news.html",
        {
            "request": request,
            "meldungen": meldungen,
            "cluster": cluster,
            "mediennamen": mediennamen,
            "medien": medien,
            "parteinamen": parteinamen,
        },
    )


@router.get("/medien", response_class=HTMLResponse)
def medien_seite(request: Request, db: Session = Depends(get_db)):
    """Medien-Transparenz: Orientierung + Vertrauensstufe je Quelle, inkl. der
    ausgeschlossenen Satire-/Fake-/Propaganda-Quellen (zu Wissenszwecken)."""
    quellen = db.scalars(select(Quelle).order_by(Quelle.medienname)).all()
    serioes = [q for q in quellen if q.vertrauensstufe == Vertrauensstufe.serioes]
    mit_vorsicht = [q for q in quellen if q.vertrauensstufe == Vertrauensstufe.mit_vorsicht]
    ausgeschlossen = [q for q in quellen if q.vertrauensstufe == Vertrauensstufe.ausgeschlossen]
    return templates.TemplateResponse(
        "medien.html",
        {
            "request": request,
            "serioes": serioes,
            "mit_vorsicht": mit_vorsicht,
            "ausgeschlossen": ausgeschlossen,
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
