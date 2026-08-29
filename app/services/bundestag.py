"""Parser/Import für Bundestag Open Data – namentliche Abstimmungen (Punkt 5).

Der Bundestag veröffentlicht namentliche Abstimmungen als Datei je Abstimmung
(XLSX und XML) mit den Spalten Vorname, Name (Nachname), Fraktion sowie den
Ja/Nein/Enthaltung/Nichtabgegeben-Markierungen. Es gibt kein REST-Vote-API.

Dieser Parser ist bewusst tolerant: Er sucht Personensätze anhand ihrer
Stimmspalten und liest Namen/Fraktion case-insensitiv aus den direkten
Kindelementen. Getestet gegen eine Fixture im offiziellen Spaltenschema.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.enums import AuditAktion, Stimme
from app.models import Abstimmung, Politiker

_STIMM_SPALTEN = {"ja", "nein", "enthaltung", "enthalten", "nichtabgegeben",
                  "nicht_abgegeben", "ungueltig", "ungültig"}
_NAME_SPALTEN = {"vorname", "name", "nachname"}
_WAHR = {"1", "x", "ja", "true", "wahr"}


@dataclass
class AbstimmungRoh:
    vorname: str | None
    nachname: str | None
    fraktion: str | None
    stimme: Stimme


@dataclass
class AbstimmungMeta:
    thema: str | None = None
    datum: dt.date | None = None
    wahlperiode: str | None = None
    saetze: list[AbstimmungRoh] = field(default_factory=list)


def _kinder(el) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind in el:
        tag = kind.tag.split("}")[-1].lower()
        out[tag] = (kind.text or "").strip()
    return out


def _wahr(wert: str | None) -> bool:
    return bool(wert) and wert.strip().lower() in _WAHR


def _stimme_aus(kinder: dict[str, str]) -> Stimme:
    if _wahr(kinder.get("ja")):
        return Stimme.dafuer
    if _wahr(kinder.get("nein")):
        return Stimme.dagegen
    if _wahr(kinder.get("enthaltung")) or _wahr(kinder.get("enthalten")):
        return Stimme.enthalten
    return Stimme.nicht_anwesend


def _finde_text(wurzel, tags: set[str]) -> str | None:
    for el in wurzel.iter():
        tag = el.tag.split("}")[-1].lower()
        if tag in tags and el.text and el.text.strip():
            return el.text.strip()
    return None


def _parse_datum(roh: str | None) -> dt.date | None:
    if not roh:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(roh.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_namentliche_abstimmung(inhalt: str | bytes) -> AbstimmungMeta:
    if isinstance(inhalt, bytes):
        inhalt = inhalt.decode("utf-8", errors="replace")
    wurzel = ET.fromstring(inhalt)

    meta = AbstimmungMeta(
        thema=_finde_text(wurzel, {"abstimmungstitel", "titel", "thema", "bezeichnung"}),
        datum=_parse_datum(_finde_text(wurzel, {"abstimmungsdatum", "datum"})),
        wahlperiode=_finde_text(wurzel, {"wahlperiode"}),
    )

    for el in wurzel.iter():
        kinder = _kinder(el)
        if not (_STIMM_SPALTEN & kinder.keys()):
            continue
        if not (_NAME_SPALTEN & kinder.keys()):
            continue
        meta.saetze.append(AbstimmungRoh(
            vorname=kinder.get("vorname"),
            nachname=kinder.get("nachname") or kinder.get("name"),
            fraktion=kinder.get("fraktion") or kinder.get("gruppe"),
            stimme=_stimme_aus(kinder),
        ))
    return meta


def import_abstimmungen(
    db: Session, meta: AbstimmungMeta, *, quelle_url: str | None = None
) -> int:
    """Importiert Stimmen für bereits bekannte Politiker (Match über Namen).

    Politiker, die nicht in der DB sind, werden übersprungen (keine Anlage aus
    Abstimmungsdaten). Rückgabe: Zahl importierter Stimmen.
    """
    politiker = db.scalars(select(Politiker)).all()
    index: dict[tuple[str, str], Politiker] = {}
    for p in politiker:
        teile = p.name.split()
        if len(teile) >= 2:
            index[(teile[0].lower(), teile[-1].lower())] = p

    thema = meta.thema or "Namentliche Abstimmung"
    importiert = 0
    for satz in meta.saetze:
        if not satz.vorname or not satz.nachname:
            continue
        pol = index.get((satz.vorname.lower(), satz.nachname.lower()))
        if pol is None:
            continue
        db.add(Abstimmung(
            politiker_id=pol.id, thema=thema, datum=meta.datum,
            stimme=satz.stimme, quelle_url=quelle_url,
        ))
        db.flush()
        importiert += 1
    if importiert:
        audit(db, tabelle="abstimmungen", datensatz_id=None,
              aktion=AuditAktion.erstellt, akteur="bundestag-import")
    return importiert
