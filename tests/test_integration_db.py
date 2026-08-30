"""DB-Integrationstests (laufen nur mit erreichbarer Postgres+pgvector-DB).

Decken den vollen Durchstich ab, den die Unit-Tests nicht sehen:
3-Quellen-Statuswechsel über die API, News-Dedup/Clustering, Vier-Augen-
Snapshot-Prüfung und die belegpflichtige RAG-Antwort.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.core.ner import GazetteerTagger
from app.enums import Ereigniskategorie, SnapshotStatus, Vertrauensstufe
from app.feeds import Feed
from app.models import (
    ArtikelSnapshot,
    Ereignis,
    EreignisQuelle,
    Partei,
    Quelle,
)
from app.services.news import ingest_feed_inhalt
from app.services.rag import index_ereignis


def _partei(db, name="Testpartei"):
    p = Partei(name=name, gruendungsjahr=2013)
    db.add(p)
    db.flush()
    return p


def _quelle(db, name):
    q = Quelle(medienname=name, vertrauensstufe=Vertrauensstufe.serioes)
    db.add(q)
    db.flush()
    return q


# --- 3-Quellen-Regel über die API ----------------------------------------
def test_drei_quellen_statuswechsel_via_api(db, client):
    partei = _partei(db)
    quellen = [_quelle(db, n) for n in ("dpa", "FAZ", "Reuters")]

    r = client.post("/api/ereignisse", json={
        "partei_id": str(partei.id),
        "titel": "Testkontroverse",
        "kategorie": "kontroverse",
    })
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["status"] == "vorlaeufig"

    status_verlauf = []
    for q in quellen:
        rr = client.post(f"/api/ereignisse/{eid}/quellen", json={
            "quelle_id": str(q.id),
            "artikel_url": f"https://example.com/{q.medienname}",
            "artikel_titel": f"Bericht {q.medienname}",
        })
        assert rr.status_code == 201
        status_verlauf.append(rr.json()["status"])

    # Nach der 3. unabhängigen Quelle: bestätigt.
    assert status_verlauf == ["vorlaeufig", "vorlaeufig", "bestaetigt"]


# --- News-Aggregation: Dedup + Framing-Cluster ---------------------------
def test_news_dedup_und_cluster(db):
    tagger = GazetteerTagger.aus_db(db)
    faz = """<rss version="2.0"><channel>
<item><title>Streit um die Rentenreform im Bundestag eskaliert</title>
<link>https://faz.net/x1</link><description>Debatte zur Rente.</description></item>
</channel></rss>"""
    sz = """<rss version="2.0"><channel>
<item><title>Rentenreform: Streit im Bundestag eskaliert weiter</title>
<link>https://sz.de/x1</link><description>Debatte zur Rente.</description></item>
</channel></rss>"""
    # Exaktes Titel-Duplikat der FAZ-Meldung über eine dritte Quelle.
    dup = """<rss version="2.0"><channel>
<item><title>Streit um die Rentenreform im Bundestag eskaliert</title>
<link>https://welt.de/x1</link><description>Kopie.</description></item>
</channel></rss>"""

    assert ingest_feed_inhalt(db, Feed("FAZ", "x", "https://faz.net"), faz, tagger) == 1
    assert ingest_feed_inhalt(db, Feed("SZ", "x", "https://sz.de"), sz, tagger) == 1
    assert ingest_feed_inhalt(db, Feed("Welt", "x", "https://welt.de"), dup, tagger) == 0
    db.flush()

    # Robust gegenüber vorhandenen Daten: FAZ- und SZ-Meldung teilen sich denselben
    # Cluster (Framing derselben Story), der mindestens zwei unabhängige Quellen hat.
    from app.models import Meldung
    faz_m = db.scalar(select(Meldung).where(Meldung.url == "https://faz.net/x1"))
    sz_m = db.scalar(select(Meldung).where(Meldung.url == "https://sz.de/x1"))
    assert faz_m.cluster_id is not None
    assert faz_m.cluster_id == sz_m.cluster_id
    quellen_im_cluster = {
        m.quelle_id
        for m in db.scalars(select(Meldung).where(Meldung.cluster_id == faz_m.cluster_id)).all()
    }
    assert len(quellen_im_cluster) >= 2


# --- Vier-Augen-Snapshot-Prüfung über die API ----------------------------
def test_snapshot_pruefung_via_api(db, client):
    partei = _partei(db)
    quelle = _quelle(db, "dpa")
    ereignis = Ereignis(partei_id=partei.id, titel="E", kategorie=Ereigniskategorie.kontroverse)
    db.add(ereignis)
    db.flush()
    eq = EreignisQuelle(ereignis_id=ereignis.id, quelle_id=quelle.id, artikel_url="https://x/1")
    db.add(eq)
    db.flush()
    snap = ArtikelSnapshot(
        ereignis_quelle_id=eq.id,
        status=SnapshotStatus.moeglicherweise_veraendert,
    )
    db.add(snap)
    db.flush()

    assert len(client.get("/api/snapshots/offen").json()) >= 1
    bad = client.post(f"/api/snapshots/{snap.id}/pruefen",
                      json={"status": "moeglicherweise_veraendert", "geprueft_von": "R"})
    assert bad.status_code == 422
    ok = client.post(f"/api/snapshots/{snap.id}/pruefen",
                     json={"status": "bestaetigt_veraendert", "geprueft_von": "Redaktion"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "bestaetigt_veraendert"
    assert "Redaktion" in ok.json()["geprueft_von"]


# --- RAG: Treffer + belegte Antwort --------------------------------------
def test_rag_query_liefert_beleg(db, client):
    partei = _partei(db)
    quelle = _quelle(db, "dpa")
    ereignis = Ereignis(
        partei_id=partei.id,
        titel="Kontroverse um die Rentenpolitik",
        beschreibung="Debatte über die Rentenpolitik der Partei.",
        kategorie=Ereigniskategorie.kontroverse,
    )
    db.add(ereignis)
    db.flush()
    db.add(EreignisQuelle(
        ereignis_id=ereignis.id, quelle_id=quelle.id,
        artikel_url="https://example.com/rente", artikel_titel="Rente",
    ))
    db.flush()
    db.refresh(ereignis)
    index_ereignis(db, ereignis)
    db.flush()

    r = client.post("/api/fragen", json={"frage": "Rentenpolitik der Partei", "top_k": 3})
    assert r.status_code == 200
    daten = r.json()
    assert daten["treffer"], "erwartet mindestens einen Treffer"
    assert "https://example.com/rente" in daten["antwort_text"]  # Zitats-Pflicht
