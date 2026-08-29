"""RAG-Frage-Endpunkt – "wurde das schon besprochen?" (Konzept 3.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import BelegOut, FrageAntwortOut, FrageIn, TrefferOut
from app.services import rag

router = APIRouter(prefix="/fragen", tags=["fragen"])


@router.post("", response_model=FrageAntwortOut)
def frage_stellen(daten: FrageIn, db: Session = Depends(get_db)):
    antwort = rag.frage_stellen(db, daten.frage, top_k=daten.top_k)
    return FrageAntwortOut(
        frage=antwort.frage,
        schon_besprochen=antwort.schon_besprochen,
        aehnliche_fragen_gefunden=antwort.aehnliche_fragen_gefunden,
        antwort_text=rag.formuliere_antwort(antwort),
        treffer=[
            TrefferOut(
                ereignis_id=t.ereignis.id,
                titel=t.ereignis.titel,
                kategorie=t.ereignis.kategorie,
                status=t.ereignis.status,
                distanz=round(t.distanz, 4),
                konfidenz_quellen=t.konfidenz_quellen,
                belege=[
                    BelegOut(
                        medienname=b.medienname,
                        artikel_titel=b.artikel_titel,
                        artikel_url=b.artikel_url,
                    )
                    for b in t.belege
                ],
            )
            for t in antwort.treffer
        ],
    )
