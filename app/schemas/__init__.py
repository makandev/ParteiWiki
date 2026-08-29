"""Pydantic-Schemas (API-Ein-/Ausgaben)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    Ereigniskategorie,
    Ereignisstatus,
    SnapshotStatus,
    Stimme,
    Vertrauensstufe,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Partei ---------------------------------------------------------------
class ParteiBase(BaseModel):
    name: str
    kurzbeschreibung: str | None = None
    gruendungsjahr: int | None = None
    programm_url: str | None = None
    letzte_aktualisierung: dt.date | None = None


class ParteiCreate(ParteiBase):
    pass


class ParteiOut(ORMModel, ParteiBase):
    id: uuid.UUID


# --- Politiker ------------------------------------------------------------
class PolitikerBase(BaseModel):
    name: str
    amt: str | None = None
    aktiv: bool = True


class PolitikerCreate(PolitikerBase):
    partei_id: uuid.UUID


class PolitikerOut(ORMModel, PolitikerBase):
    id: uuid.UUID
    partei_id: uuid.UUID


# --- Quelle ---------------------------------------------------------------
class QuelleBase(BaseModel):
    medienname: str
    url_basis: str | None = None
    vertrauensstufe: Vertrauensstufe = Vertrauensstufe.serioes
    ausschluss_begruendung: str | None = None


class QuelleCreate(QuelleBase):
    pass


class QuelleOut(ORMModel, QuelleBase):
    id: uuid.UUID


# --- Ereignis / Quellen-Verknüpfung --------------------------------------
class EreignisBase(BaseModel):
    partei_id: uuid.UUID
    politiker_id: uuid.UUID | None = None
    titel: str
    beschreibung: str | None = None
    kategorie: Ereigniskategorie
    datum_ereignis: dt.date | None = None
    gegendarstellung_url: str | None = None


class EreignisCreate(EreignisBase):
    pass


class EreignisQuelleCreate(BaseModel):
    quelle_id: uuid.UUID
    artikel_url: str
    artikel_titel: str | None = None


class EreignisQuelleOut(ORMModel):
    id: uuid.UUID
    quelle_id: uuid.UUID
    artikel_url: str
    artikel_titel: str | None = None
    erfasst_am: dt.date


class EreignisOut(ORMModel, EreignisBase):
    id: uuid.UUID
    status: Ereignisstatus
    datum_erfasst: dt.date
    ereignis_quellen: list[EreignisQuelleOut] = Field(default_factory=list)
    anzahl_unabhaengige_quellen: int = 0


# --- Positions-Historie ---------------------------------------------------
class PositionsHistorieBase(BaseModel):
    partei_id: uuid.UUID
    thema: str
    position_alt: str | None = None
    position_neu: str | None = None
    geaendert_am: dt.date | None = None
    quelle_url: str | None = None


class PositionsHistorieCreate(PositionsHistorieBase):
    pass


class PositionsHistorieOut(ORMModel, PositionsHistorieBase):
    id: uuid.UUID


# --- Abstimmung -----------------------------------------------------------
class AbstimmungBase(BaseModel):
    politiker_id: uuid.UUID
    thema: str
    datum: dt.date | None = None
    stimme: Stimme
    quelle_url: str | None = None


class AbstimmungCreate(AbstimmungBase):
    pass


class AbstimmungOut(ORMModel, AbstimmungBase):
    id: uuid.UUID


# --- Snapshot -------------------------------------------------------------
class SnapshotOut(ORMModel):
    id: uuid.UUID
    ereignis_quelle_id: uuid.UUID
    snapshot_datum: dt.datetime
    content_hash: str | None = None
    wayback_url: str | None = None
    status: SnapshotStatus
    geprueft_von: str | None = None


# --- Methodik-Changelog ---------------------------------------------------
class MethodikChangelogBase(BaseModel):
    was_geaendert: str
    warum: str | None = None


class MethodikChangelogCreate(MethodikChangelogBase):
    pass


class MethodikChangelogOut(ORMModel, MethodikChangelogBase):
    id: uuid.UUID
    datum: dt.date


# --- RAG-Frage ------------------------------------------------------------
class FrageIn(BaseModel):
    frage: str = Field(min_length=3)
    top_k: int = 5


class TrefferOut(BaseModel):
    ereignis_id: uuid.UUID
    titel: str
    kategorie: Ereigniskategorie
    status: Ereignisstatus
    distanz: float
    konfidenz_quellen: int


class FrageAntwortOut(BaseModel):
    frage: str
    schon_besprochen: bool
    aehnliche_fragen_gefunden: int
    treffer: list[TrefferOut]
