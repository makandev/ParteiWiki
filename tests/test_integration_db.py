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
from app.services.abgeordnetenwatch import MandatRoh, import_mdb
from app.models import Politiker
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


# --- MdB-Import (Mandate) über Partei-Normalisierung ---------------------
def _partei_or_create(db, name):
    p = db.scalar(select(Partei).where(Partei.name == name))
    if p is None:
        p = _partei(db, name=name)
    return p


def test_import_mdb_ordnet_und_ist_idempotent(db):
    afd = _partei_or_create(db, "AfD")
    gruene = _partei_or_create(db, "Grüne")
    # Test-eigene Namen, damit vorhandene Seed-Politiker den Test nicht stören.
    n1, n2 = "Testperson Eins-MdB", "Testperson Zwei-MdB"
    mandate = [
        MandatRoh(externe_id=1, politiker_name=n1, partei_label="AfD"),
        MandatRoh(externe_id=2, politiker_name=n2,
                  partei_label="BÜNDNIS 90/DIE GRÜNEN"),
        # Unbekannte Partei -> übersprungen (kein Rateverfahren).
        MandatRoh(externe_id=3, politiker_name="Niemand-MdB", partei_label="XYZ-Partei"),
    ]
    ergebnis = import_mdb(db, mandate)
    db.flush()
    assert ergebnis.get("AfD") == 1
    assert ergebnis.get("Grüne") == 1
    assert ergebnis["_uebersprungen"] == 1

    p1 = db.scalar(select(Politiker).where(Politiker.name == n1))
    assert p1 is not None and p1.partei_id == afd.id and p1.amt == "MdB"
    p2 = db.scalar(select(Politiker).where(Politiker.name == n2))
    assert p2.partei_id == gruene.id

    # Re-Import legt niemanden doppelt an.
    ergebnis2 = import_mdb(db, mandate)
    db.flush()
    assert ergebnis2.get("AfD", 0) == 0 and ergebnis2.get("Grüne", 0) == 0
    anzahl = len(db.scalars(select(Politiker).where(Politiker.name == n1)).all())
    assert anzahl == 1


# --- Kennzahlen (Wahlergebnisse, quellenpflichtig, idempotent) -----------
def test_ensure_kennzahlen_idempotent_und_belegt(db):
    from app.enums import Kennzahlart
    from app.models import Kennzahl
    from scripts.seed_kennzahlen import ensure_kennzahlen

    # Parteien anlegen, die die Seed-Daten erwarten.
    for name in ("SPD", "CDU", "AfD", "Grüne"):
        _partei_or_create(db, name)
    db.flush()

    ensure_kennzahlen(db)
    kennzahlen = db.scalars(
        select(Kennzahl).where(Kennzahl.art == Kennzahlart.bundestagswahl_zweitstimme)
    ).all()
    assert kennzahlen, "erwarte angelegte Wahlergebnis-Kennzahlen"
    # Redaktionelle Kern-Invariante: jede Zahl hat eine Quelle.
    assert all(k.quelle_url for k in kennzahlen)

    anzahl_vorher = len(kennzahlen)
    ensure_kennzahlen(db)  # zweiter Lauf -> aktualisiert, dupliziert nicht
    anzahl_nachher = len(db.scalars(
        select(Kennzahl).where(Kennzahl.art == Kennzahlart.bundestagswahl_zweitstimme)
    ).all())
    assert anzahl_nachher == anzahl_vorher


# --- Vergleich-Seite: Wahlergebnisse + Trend nebeneinander ---------------
def test_vergleich_seite_zeigt_wahlergebnisse(db, client):
    from scripts.seed_kennzahlen import ensure_kennzahlen

    for name in ("CDU", "AfD", "SPD"):
        _partei_or_create(db, name)
    db.flush()
    ensure_kennzahlen(db)

    r = client.get("/vergleich")
    assert r.status_code == 200
    t = r.text
    assert "Parteien im Vergleich" in t
    # Deutsches Zahlenformat (Komma) und Trend-Symbol vorhanden.
    assert "22,6" in t and ("▲" in t or "▼" in t)


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
