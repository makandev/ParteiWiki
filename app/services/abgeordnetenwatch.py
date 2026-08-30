"""Client für die abgeordnetenwatch.de API v2 (Konzept, Datenquelle Punkt 5).

Liefert Politiker-Stammdaten und Bürgerfragen/-antworten. Parsing und Persistenz
sind vom Netzabruf getrennt, damit sie deterministisch (gegen Fixtures) testbar
sind – der Live-Abruf ist in dieser Umgebung ohnehin durch die Egress-Policy
gesperrt.

API-Form (v2):
    GET {BASE}/politicians?range_start=0&range_end=100
    -> {"meta": {...}, "data": [ {id, label, first_name, last_name,
                                  party: {id, label}, ...}, ... ]}
    GET {BASE}/questions?politician={id}
    -> {"meta": {...}, "data": [ {id, questions_text, answers:[{answer_text,...}],
                                  politician:{id,label}}, ... ]}
    GET {BASE}/candidacies-mandates?parliament_period={id}&type=mandate&range_end=1000
    -> {"meta": {...}, "data": [ {id, label, type: "mandate",
                                  politician:{id,label}, party:{id,label},
                                  fraction_membership:[{fraction:{label}}], ...}, ... ]}
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.enums import AuditAktion
from app.models import Partei, Politiker

BASE = "https://www.abgeordnetenwatch.de/api/v2"

# abgeordnetenwatch-Parteilabels -> unsere Parteinamen (scripts/seed_parteien.py).
# Bewusst konservativ: nur eindeutige, gut belegte Zuordnungen. Unbekannte
# Labels bleiben unzugeordnet (kein Rateverfahren).
PARTEI_NORMALISIERUNG: dict[str, str] = {
    "cdu": "CDU",
    "csu": "CSU",
    "spd": "SPD",
    "grüne": "Grüne",
    "bündnis 90/die grünen": "Grüne",
    "die grünen": "Grüne",
    "fdp": "FDP",
    "afd": "AfD",
    "alternative für deutschland": "AfD",
    "die linke": "Die Linke",
    "die linke.": "Die Linke",
    "linke": "Die Linke",
    "bsw": "BSW",
    "bündnis sahra wagenknecht": "BSW",
    "freie wähler": "Freie Wähler",
}


def normalisiere_partei(label: str | None) -> str | None:
    """Mappt ein abgeordnetenwatch-Parteilabel auf unseren Parteinamen."""
    if not label:
        return None
    return PARTEI_NORMALISIERUNG.get(label.strip().casefold())


@dataclass
class PolitikerRoh:
    externe_id: int | None
    name: str
    vorname: str | None = None
    nachname: str | None = None
    partei_label: str | None = None


@dataclass
class PeriodeRoh:
    """Eine Legislaturperiode (zur automatischen Auswahl der aktuellen)."""
    externe_id: int | None
    label: str | None
    parlament_label: str | None
    start_datum: str | None = None


@dataclass
class MandatRoh:
    """Ein Bundestagsmandat: Person + (normalisierbare) Partei."""
    externe_id: int | None
    politiker_name: str
    politiker_externe_id: int | None = None
    partei_label: str | None = None


@dataclass
class AntwortRoh:
    text: str
    datum: str | None = None


@dataclass
class FrageRoh:
    externe_id: int | None
    frage_text: str
    politiker_label: str | None
    antworten: list[AntwortRoh] = field(default_factory=list)


def parse_politicians(payload: dict) -> list[PolitikerRoh]:
    ergebnis: list[PolitikerRoh] = []
    for d in payload.get("data", []):
        partei = d.get("party") or {}
        ergebnis.append(PolitikerRoh(
            externe_id=d.get("id"),
            name=d.get("label") or " ".join(
                filter(None, [d.get("first_name"), d.get("last_name")])
            ),
            vorname=d.get("first_name"),
            nachname=d.get("last_name"),
            partei_label=partei.get("label") if isinstance(partei, dict) else None,
        ))
    return ergebnis


def parse_parliament_periods(payload: dict) -> list[PeriodeRoh]:
    """Extrahiert Legislaturperioden aus einer parliament-periods-Antwort."""
    ergebnis: list[PeriodeRoh] = []
    for d in payload.get("data", []):
        parlament = d.get("parliament") or {}
        ergebnis.append(PeriodeRoh(
            externe_id=d.get("id"),
            label=d.get("label"),
            parlament_label=parlament.get("label") if isinstance(parlament, dict) else None,
            start_datum=d.get("start_date_period"),
        ))
    return ergebnis


def waehle_aktuelle_periode(
    perioden: list[PeriodeRoh], *, parlament: str = "Bundestag"
) -> PeriodeRoh | None:
    """Wählt die jüngste Legislaturperiode des genannten Parlaments.

    Auswahl über das Startdatum (jüngstes zuerst); fehlt es, dient die
    externe ID als Ersatzkriterium (höhere ID = neuer).
    """
    passende = [
        p for p in perioden
        if p.externe_id is not None
        and (p.parlament_label or "").casefold() == parlament.casefold()
    ]
    if not passende:
        return None
    return max(passende, key=lambda p: (p.start_datum or "", p.externe_id or 0))


def _partei_aus_mandat(d: dict) -> str | None:
    """Ermittelt das Parteilabel eines Mandats – bevorzugt ``party``,
    ersatzweise die Fraktionszugehörigkeit."""
    partei = d.get("party")
    if isinstance(partei, dict) and partei.get("label"):
        return partei["label"]
    for fm in d.get("fraction_membership") or []:
        fraktion = fm.get("fraction") if isinstance(fm, dict) else None
        if isinstance(fraktion, dict) and fraktion.get("label"):
            return fraktion["label"]
    return None


def parse_mandate(payload: dict) -> list[MandatRoh]:
    """Extrahiert Mandate (type == 'mandate') aus einer candidacies-mandates-Antwort."""
    ergebnis: list[MandatRoh] = []
    for d in payload.get("data", []):
        if d.get("type") not in (None, "mandate"):
            continue
        pol = d.get("politician") or {}
        pol_name = pol.get("label") if isinstance(pol, dict) else None
        if not pol_name:
            continue
        ergebnis.append(MandatRoh(
            externe_id=d.get("id"),
            politiker_name=pol_name,
            politiker_externe_id=pol.get("id") if isinstance(pol, dict) else None,
            partei_label=_partei_aus_mandat(d),
        ))
    return ergebnis


def parse_questions(payload: dict) -> list[FrageRoh]:
    ergebnis: list[FrageRoh] = []
    for d in payload.get("data", []):
        pol = d.get("politician") or {}
        antworten = [
            AntwortRoh(text=a.get("answer_text", ""), datum=a.get("date"))
            for a in d.get("answers", [])
            if a.get("answer_text")
        ]
        ergebnis.append(FrageRoh(
            externe_id=d.get("id"),
            frage_text=d.get("questions_text") or d.get("label", ""),
            politiker_label=pol.get("label") if isinstance(pol, dict) else None,
            antworten=antworten,
        ))
    return ergebnis


def import_politicians(
    db: Session, partei: Partei, rohdaten: list[PolitikerRoh], *, amt: str | None = "MdB"
) -> int:
    """Legt fehlende Politiker der Partei an (Match über Name). Rückgabe: neue."""
    vorhanden = {
        p.name for p in db.scalars(
            select(Politiker).where(Politiker.partei_id == partei.id)
        ).all()
    }
    neu = 0
    for roh in rohdaten:
        if not roh.name or roh.name in vorhanden:
            continue
        pol = Politiker(partei_id=partei.id, name=roh.name, amt=amt, aktiv=True)
        db.add(pol)
        db.flush()
        audit(db, tabelle="politiker", datensatz_id=pol.id,
              aktion=AuditAktion.erstellt, akteur="abgeordnetenwatch")
        vorhanden.add(roh.name)
        neu += 1
    return neu


def import_mdb(db: Session, mandate: list[MandatRoh], *, amt: str = "MdB") -> dict[str, int]:
    """Legt fehlende MdBs je Partei an (Zuordnung über normalisiertes Parteilabel).

    Mandate mit unbekannter Partei oder ohne passenden Partei-Datensatz werden
    übersprungen (kein Rateverfahren – gleiche Methodik für alle). Rückgabe:
    ``{parteiname: neu_angelegt}`` plus ``"_uebersprungen"``.
    """
    parteien = {p.name: p for p in db.scalars(select(Partei)).all()}
    # Bestehende Namen je Partei-ID, damit Re-Import idempotent bleibt.
    vorhanden: dict[int, set[str]] = {}
    for p in parteien.values():
        vorhanden[p.id] = {
            pol.name for pol in db.scalars(
                select(Politiker).where(Politiker.partei_id == p.id)
            ).all()
        }
    ergebnis: dict[str, int] = {}
    uebersprungen = 0
    for m in mandate:
        parteiname = normalisiere_partei(m.partei_label)
        partei = parteien.get(parteiname) if parteiname else None
        if partei is None or not m.politiker_name:
            uebersprungen += 1
            continue
        if m.politiker_name in vorhanden[partei.id]:
            continue
        pol = Politiker(partei_id=partei.id, name=m.politiker_name, amt=amt, aktiv=True)
        db.add(pol)
        db.flush()
        audit(db, tabelle="politiker", datensatz_id=pol.id,
              aktion=AuditAktion.erstellt, akteur="abgeordnetenwatch:mandate")
        vorhanden[partei.id].add(m.politiker_name)
        ergebnis[partei.name] = ergebnis.get(partei.name, 0) + 1
    ergebnis["_uebersprungen"] = uebersprungen
    return ergebnis


class AbgeordnetenwatchClient:
    """Dünner HTTP-Client mit range_start/range_end-Pagination."""

    def __init__(self, base: str = BASE, client: httpx.Client | None = None):
        self.base = base
        self._client = client or httpx.Client(
            headers={"User-Agent": "ParteiWiki/0.1"}, timeout=30
        )

    def politicians(self, *, party_id: int | None = None, limit: int = 100) -> list[PolitikerRoh]:
        params: dict = {"range_start": 0, "range_end": limit}
        if party_id is not None:
            params["party[entity.id]"] = party_id
        resp = self._client.get(f"{self.base}/politicians", params=params)
        resp.raise_for_status()
        return parse_politicians(resp.json())

    def parliament_periods(self, *, parlament: str = "Bundestag", limit: int = 50) -> list[PeriodeRoh]:
        """Legislaturperioden eines Parlaments abrufen (für die Auto-Auswahl)."""
        params = {
            "parliament[entity.label]": parlament,
            "type": "legislature",
            "range_start": 0,
            "range_end": limit,
        }
        resp = self._client.get(f"{self.base}/parliament-periods", params=params)
        resp.raise_for_status()
        return parse_parliament_periods(resp.json())

    def aktuelle_bundestag_periode(self) -> PeriodeRoh | None:
        """Ermittelt die aktuelle Bundestags-Legislaturperiode automatisch."""
        return waehle_aktuelle_periode(
            self.parliament_periods(parlament="Bundestag"), parlament="Bundestag"
        )

    def mandate(self, *, parliament_period: int, limit: int = 1000) -> list[MandatRoh]:
        """Alle Mandate einer Legislaturperiode (Bundestag) abrufen."""
        params = {
            "parliament_period": parliament_period,
            "type": "mandate",
            "range_start": 0,
            "range_end": limit,
        }
        resp = self._client.get(f"{self.base}/candidacies-mandates", params=params)
        resp.raise_for_status()
        return parse_mandate(resp.json())

    def questions(self, *, politician_id: int, limit: int = 50) -> list[FrageRoh]:
        params = {"politician": politician_id, "range_start": 0, "range_end": limit}
        resp = self._client.get(f"{self.base}/questions", params=params)
        resp.raise_for_status()
        return parse_questions(resp.json())

    def close(self) -> None:
        self._client.close()
