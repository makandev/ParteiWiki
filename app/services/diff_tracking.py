"""Diff-Tracking (Alleinstellungsmerkmal, Konzept 3.5 / Kriterien 4, 4b).

Gerüst für den Cronjob: Vergleicht die erfassten Artikel-URLs regelmäßig
gegen Wayback-Machine-Snapshots und erkennt Titel-/Inhaltsänderungen oder
Löschungen (404/410) über einen Hash des Haupttexts.

Redaktionelle Vorsicht (Kriterien 4b): Automatisch erkannte Änderungen werden
NICHT sofort als Fakt gesetzt, sondern als ``moeglicherweise_veraendert``
markiert. Erst nach manueller Prüfung (Vier-Augen-Prinzip) setzt ein Mensch
den Status auf ``bestaetigt_veraendert`` / ``entfernt``.
"""
from __future__ import annotations

import hashlib
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.audit import audit
from app.enums import AuditAktion, SnapshotStatus
from app.models import ArtikelSnapshot, EreignisQuelle

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def content_hash(html: str) -> str:
    """Hash des sichtbaren Haupttexts (Tags/Whitespace normalisiert).

    Reine Layout-/Werbe-Änderungen sollen möglichst NICHT zu einem Diff
    führen (Kriterien 4). Diese einfache Normalisierung ist ein erster
    Näherungswert und lässt sich später durch eine echte Boilerplate-
    Entfernung (z. B. trafilatura) ersetzen.
    """
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wayback_snapshot(client: httpx.Client, url: str) -> str | None:
    """Ermittelt die URL des jüngsten Wayback-Snapshots zu ``url``."""
    try:
        resp = client.get(settings.wayback_api, params={"url": url}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        closest = data.get("archived_snapshots", {}).get("closest")
        if closest and closest.get("available"):
            return closest.get("url")
    except (httpx.HTTPError, ValueError):
        return None
    return None


def pruefe_ereignis_quelle(
    db: Session, client: httpx.Client, eq: EreignisQuelle
) -> ArtikelSnapshot | None:
    """Erzeugt bei Bedarf einen neuen Snapshot für eine Artikel-URL.

    Rückgabe: der neu angelegte Snapshot, oder ``None`` wenn sich nichts
    Prüfenswertes ergeben hat.
    """
    letzter = db.scalars(
        select(ArtikelSnapshot)
        .where(ArtikelSnapshot.ereignis_quelle_id == eq.id)
        .order_by(ArtikelSnapshot.snapshot_datum.desc())
    ).first()

    snapshot_url = wayback_snapshot(client, eq.artikel_url)
    neu_status = SnapshotStatus.original
    neu_hash: str | None = None

    try:
        resp = client.get(eq.artikel_url, timeout=20, follow_redirects=True)
        if resp.status_code in (404, 410):
            neu_status = SnapshotStatus.moeglicherweise_veraendert  # ggf. entfernt
        else:
            resp.raise_for_status()
            neu_hash = content_hash(resp.text)
            if letzter and letzter.content_hash and letzter.content_hash != neu_hash:
                # Hash-Unterschied -> zunächst nur "möglicherweise" (Kriterien 4b).
                neu_status = SnapshotStatus.moeglicherweise_veraendert
    except httpx.HTTPError:
        # Nicht erreichbar: als Verdacht markieren, manuelle Prüfung entscheidet.
        neu_status = SnapshotStatus.moeglicherweise_veraendert

    # Kein erster Snapshot und nichts erreichbar -> nichts anlegen.
    if letzter is None and neu_hash is None and snapshot_url is None:
        return None

    snapshot = ArtikelSnapshot(
        ereignis_quelle_id=eq.id,
        content_hash=neu_hash,
        wayback_url=snapshot_url,
        status=neu_status,
    )
    db.add(snapshot)
    db.flush()
    audit(
        db,
        tabelle="artikel_snapshots",
        datensatz_id=snapshot.id,
        aktion=AuditAktion.erstellt,
        akteur="diff-tracking-job",
    )
    return snapshot


def pruefe_alle(db: Session) -> int:
    """Prüft alle erfassten Artikel-URLs. Rückgabe: Anzahl neuer Snapshots."""
    eqs = db.scalars(select(EreignisQuelle)).all()
    anzahl = 0
    with httpx.Client(headers={"User-Agent": "ParteiWiki-DiffTracker/0.1"}) as client:
        for eq in eqs:
            if pruefe_ereignis_quelle(db, client, eq) is not None:
                anzahl += 1
    db.commit()
    return anzahl
