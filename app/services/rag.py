"""RAG-Frage-Funktion (Konzept 3.3) – "wurde das schon besprochen?".

Gerüst der semantischen Suche über pgvector. Beim Indexieren wird pro Ereignis
ein Embedding aus ``beschreibung`` + den Artikel-Titeln gebildet und in
``ereignis_embeddings`` abgelegt. Eine Nutzerfrage wird embeddet, die
ähnlichsten Ereignisse werden per Cosinus-Distanz gesucht, und jede Antwort
verweist über ``ereignis_id`` auf konkrete Datensätze (Zitations-Pflicht).

Der Konfidenz-Score entspricht der Zahl unabhängiger Quellen des Ereignisses
("1 Quelle" vs. "5 unabhängige Quellen bestätigen").
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embeddings import get_embedder
from app.core.neutralitaet import zaehle_unabhaengige_quellen
from app.models import Ereignis, EreignisEmbedding, NutzerFrage


def quelltext_fuer(ereignis: Ereignis) -> str:
    """Baut den zu embeddenden Text aus Beschreibung + Artikel-Titeln."""
    teile = [ereignis.titel, ereignis.beschreibung or ""]
    teile += [eq.artikel_titel or "" for eq in ereignis.ereignis_quellen]
    return " \n ".join(t for t in teile if t)


def index_ereignis(db: Session, ereignis: Ereignis) -> None:
    """Legt das Embedding eines Ereignisses an oder aktualisiert es (ohne Commit)."""
    text = quelltext_fuer(ereignis)
    vektor = get_embedder().embed(text)
    vorhanden = db.get(EreignisEmbedding, ereignis.id)
    if vorhanden is None:
        db.add(EreignisEmbedding(ereignis_id=ereignis.id, quelltext=text, embedding=vektor))
    else:
        vorhanden.quelltext = text
        vorhanden.embedding = vektor


def reindex_alle(db: Session) -> int:
    """Baut den kompletten Vektor-Index neu auf. Rückgabe: Anzahl Ereignisse."""
    ereignisse = db.scalars(select(Ereignis)).all()
    for e in ereignisse:
        index_ereignis(db, e)
    db.commit()
    return len(ereignisse)


@dataclass
class Beleg:
    medienname: str
    artikel_titel: str | None
    artikel_url: str


@dataclass
class Treffer:
    ereignis: Ereignis
    distanz: float
    konfidenz_quellen: int
    belege: list[Beleg] = field(default_factory=list)


@dataclass
class Antwort:
    frage: str
    treffer: list[Treffer] = field(default_factory=list)
    aehnliche_fragen_gefunden: int = 0

    @property
    def schon_besprochen(self) -> bool:
        return bool(self.treffer)


def _belege(ereignis: Ereignis) -> list[Beleg]:
    return [
        Beleg(
            medienname=eq.quelle.medienname if eq.quelle else "unbekannt",
            artikel_titel=eq.artikel_titel,
            artikel_url=eq.artikel_url,
        )
        for eq in ereignis.ereignis_quellen
    ]


def formuliere_antwort(antwort: Antwort) -> str:
    """Belegpflichtige Antwort über den konfigurierten LLM-Layer.

    Delegiert an den Summarizer (Default: extraktiv, deterministisch, keine
    Halluzination; optional Anthropic-SDK mit striktem Zitations-Zwang). Beide
    Wege garantieren: keine Behauptung ohne Quelle.
    """
    from app.core.llm import get_summarizer  # lazy: vermeidet Import-Zyklus

    return get_summarizer().summarize(antwort)


def frage_stellen(
    db: Session, frage_text: str, *, top_k: int = 5, speichern: bool = True
) -> Antwort:
    """Beantwortet eine Nutzerfrage per Ähnlichkeitssuche über Ereignisse."""
    vektor = get_embedder().embed(frage_text)

    rows = db.execute(
        select(
            EreignisEmbedding.ereignis_id,
            EreignisEmbedding.embedding.cosine_distance(vektor).label("distanz"),
        )
        .order_by("distanz")
        .limit(top_k)
    ).all()

    treffer: list[Treffer] = []
    for ereignis_id, distanz in rows:
        ereignis = db.get(Ereignis, ereignis_id)
        if ereignis is None:
            continue
        treffer.append(
            Treffer(
                ereignis=ereignis,
                distanz=float(distanz),
                konfidenz_quellen=zaehle_unabhaengige_quellen(db, ereignis),
                belege=_belege(ereignis),
            )
        )

    # Zählen, wie oft eine ähnliche Frage schon gestellt wurde.
    aehnliche = _zaehle_aehnliche_fragen(db, vektor)

    if speichern:
        db.add(
            NutzerFrage(
                frage_text=frage_text,
                embedding=vektor,
                verknuepftes_ereignis_id=(
                    treffer[0].ereignis.id if treffer else None
                ),
                aehnliche_fragen_gefunden=aehnliche,
            )
        )
        db.commit()

    return Antwort(
        frage=frage_text, treffer=treffer, aehnliche_fragen_gefunden=aehnliche
    )


def _zaehle_aehnliche_fragen(
    db: Session, vektor: list[float], schwelle: float = 0.15
) -> int:
    """Zahl früherer Fragen mit Cosinus-Distanz unter ``schwelle``."""
    rows = db.execute(
        select(NutzerFrage.embedding.cosine_distance(vektor).label("d"))
        .where(NutzerFrage.embedding.is_not(None))
    ).all()
    return sum(1 for (d,) in rows if d is not None and float(d) < schwelle)
