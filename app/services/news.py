"""Nachrichten-Aggregation (Konzept 3.2).

Enthält:
* einen RSS/Atom-Parser auf Basis der Standardbibliothek (kein feedparser),
* Duplikat-Erkennung (exakt über einen Titel-Hash),
* Near-Duplicate-Clustering über Embeddings (Grundlage für den
  Framing-Vergleich derselben Story über verschiedene Quellen),
* automatisches NER-Tagging der Meldungen.

Der Netzabruf ist vom Parsing getrennt, damit die Verarbeitung deterministisch
gegen Fixtures testbar ist.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.embeddings import get_embedder
from app.core.ner import GazetteerTagger, tag_meldung, tagger_fuer
from app.enums import AuditAktion, Vertrauensstufe
from app.feeds import Feed
from app.models import Meldung, Quelle

# Schwelle der Cosinus-Distanz, unterhalb derer zwei Meldungen als dieselbe
# Story (unterschiedliches Framing) gelten.
CLUSTER_SCHWELLE = 0.25

_ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class FeedItem:
    titel: str
    url: str
    zusammenfassung: str | None = None
    veroeffentlicht_am: dt.datetime | None = None


def _text(el) -> str | None:
    return el.text.strip() if el is not None and el.text else None


def _parse_datum(roh: str | None) -> dt.datetime | None:
    if not roh:
        return None
    try:  # RSS: RFC-822
        return parsedate_to_datetime(roh)
    except (TypeError, ValueError):
        pass
    try:  # Atom: ISO-8601
        return dt.datetime.fromisoformat(roh.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_feed(inhalt: str | bytes) -> list[FeedItem]:
    """Parst RSS 2.0 und Atom in eine einheitliche Item-Liste."""
    if isinstance(inhalt, bytes):
        inhalt = inhalt.decode("utf-8", errors="replace")
    wurzel = ET.fromstring(inhalt)

    items: list[FeedItem] = []

    # RSS 2.0: channel/item
    for item in wurzel.iter("item"):
        titel = _text(item.find("title"))
        link = _text(item.find("link"))
        if not titel or not link:
            continue
        items.append(FeedItem(
            titel=titel,
            url=link,
            zusammenfassung=_text(item.find("description")),
            veroeffentlicht_am=_parse_datum(_text(item.find("pubDate"))),
        ))

    # Atom: feed/entry
    for entry in wurzel.iter(f"{_ATOM}entry"):
        titel = _text(entry.find(f"{_ATOM}title"))
        link_el = entry.find(f"{_ATOM}link")
        link = link_el.get("href") if link_el is not None else None
        if not titel or not link:
            continue
        summary = _text(entry.find(f"{_ATOM}summary")) or _text(entry.find(f"{_ATOM}content"))
        datum = _parse_datum(_text(entry.find(f"{_ATOM}updated")) or _text(entry.find(f"{_ATOM}published")))
        items.append(FeedItem(titel=titel, url=link, zusammenfassung=summary, veroeffentlicht_am=datum))

    return items


def _titel_hash(titel: str) -> str:
    norm = " ".join(titel.lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _finde_cluster(db: Session, embedding: list[float]) -> uuid.UUID:
    """Ordnet die Meldung einem bestehenden Cluster zu oder eröffnet ein neues.

    Zwei Meldungen unter der Cluster-Schwelle gelten als dieselbe Story –
    Grundlage für den Framing-Vergleich zwischen Quellen.
    """
    row = db.execute(
        select(
            Meldung.cluster_id,
            Meldung.embedding.cosine_distance(embedding).label("d"),
        )
        .where(Meldung.embedding.is_not(None), Meldung.cluster_id.is_not(None))
        .order_by("d")
        .limit(1)
    ).first()
    if row is not None and row.d is not None and float(row.d) < CLUSTER_SCHWELLE:
        return row.cluster_id
    return uuid.uuid4()


def ingest_item(
    db: Session, quelle: Quelle, item: FeedItem, tagger: GazetteerTagger
) -> Meldung | None:
    """Legt eine Meldung an (mit Dedup, Clustering, Tagging). Ohne Commit.

    Rückgabe ``None``, wenn die Meldung bereits existiert (URL oder Titel-Hash).
    """
    if db.scalar(select(Meldung).where(Meldung.url == item.url)):
        return None
    h = _titel_hash(item.titel)
    if db.scalar(select(Meldung).where(Meldung.inhalt_hash == h)):
        # Exaktes Duplikat (z. B. weiterverbreitete Agenturmeldung) – überspringen.
        return None

    embedding = get_embedder().embed(f"{item.titel} {item.zusammenfassung or ''}")
    cluster_id = _finde_cluster(db, embedding)

    meldung = Meldung(
        quelle_id=quelle.id,
        titel=item.titel,
        url=item.url,
        zusammenfassung=item.zusammenfassung,
        veroeffentlicht_am=item.veroeffentlicht_am,
        inhalt_hash=h,
        cluster_id=cluster_id,
        embedding=embedding,
    )
    db.add(meldung)
    db.flush()
    tag_meldung(db, meldung, tagger)
    audit(db, tabelle="meldungen", datensatz_id=meldung.id,
          aktion=AuditAktion.erstellt, akteur="news-ingest")
    return meldung


def _hole_quelle(db: Session, feed: Feed) -> Quelle:
    quelle = db.scalar(select(Quelle).where(Quelle.medienname == feed.medienname))
    if quelle is None:
        quelle = Quelle(
            medienname=feed.medienname,
            url_basis=feed.url_basis,
            vertrauensstufe=Vertrauensstufe.serioes,
        )
        db.add(quelle)
        db.flush()
    return quelle


def ingest_feed_inhalt(
    db: Session, feed: Feed, inhalt: str | bytes, tagger: GazetteerTagger
) -> int:
    """Verarbeitet den bereits geladenen Inhalt eines Feeds. Rückgabe: neue Meldungen."""
    quelle = _hole_quelle(db, feed)
    if quelle.vertrauensstufe == Vertrauensstufe.ausgeschlossen:
        return 0
    anzahl = 0
    for item in parse_feed(inhalt):
        if ingest_item(db, quelle, item, tagger) is not None:
            anzahl += 1
    return anzahl


def fetch_and_ingest(db: Session, feeds: list[Feed]) -> dict[str, int]:
    """Lädt und verarbeitet alle Feeds. Rückgabe: {medienname: neue Meldungen}."""
    tagger = tagger_fuer(db)
    ergebnis: dict[str, int] = {}
    with httpx.Client(
        headers={"User-Agent": "ParteiWiki-NewsIngest/0.1"}, timeout=20,
        follow_redirects=True,
    ) as client:
        for feed in feeds:
            try:
                resp = client.get(feed.url)
                resp.raise_for_status()
                ergebnis[feed.medienname] = ingest_feed_inhalt(
                    db, feed, resp.content, tagger
                )
            except httpx.HTTPError as exc:
                ergebnis[feed.medienname] = -1  # Abruf fehlgeschlagen
                print(f"  ! {feed.medienname}: {exc}")
    db.commit()
    return ergebnis
