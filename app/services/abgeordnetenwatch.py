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


@dataclass
class PolitikerRoh:
    externe_id: int | None
    name: str
    vorname: str | None = None
    nachname: str | None = None
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

    def questions(self, *, politician_id: int, limit: int = 50) -> list[FrageRoh]:
        params = {"politician": politician_id, "range_start": 0, "range_end": limit}
        resp = self._client.get(f"{self.base}/questions", params=params)
        resp.raise_for_status()
        return parse_questions(resp.json())

    def close(self) -> None:
        self._client.close()
