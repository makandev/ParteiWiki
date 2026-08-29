"""ORM-Modelle – 1:1 zum Datenmodell-Entwurf (Postgres + pgvector).

Ein Modul, damit Fremdschlüssel und Relationen an einer Stelle sichtbar
zusammenhängen:

    Partei ──< Politiker ──< Ereignisse >── Quellen
                                 │
                                 └──< EreignisQuelle ──< ArtikelSnapshot
"""
from __future__ import annotations

import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base
from app.enums import (
    AuditAktion,
    Ereigniskategorie,
    Ereignisstatus,
    SnapshotStatus,
    Stimme,
    TagMethode,
    Vertrauensstufe,
)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _enum(py_enum, **kw):
    # native_enum=False -> portable VARCHAR + CHECK-Constraint statt PG-Enum-Typ.
    return SAEnum(py_enum, native_enum=False, validate_strings=True, **kw)


class Partei(Base):
    """1. parteien"""

    __tablename__ = "parteien"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kurzbeschreibung: Mapped[str | None] = mapped_column(Text)  # neutral, faktenbasiert
    gruendungsjahr: Mapped[int | None] = mapped_column(Integer)
    programm_url: Mapped[str | None] = mapped_column(Text)
    letzte_aktualisierung: Mapped[dt.date | None] = mapped_column(Date)

    politiker: Mapped[list["Politiker"]] = relationship(
        back_populates="partei", cascade="all, delete-orphan"
    )
    ereignisse: Mapped[list["Ereignis"]] = relationship(back_populates="partei")
    positionen: Mapped[list["PositionsHistorie"]] = relationship(
        back_populates="partei", cascade="all, delete-orphan"
    )


class Politiker(Base):
    """2. politiker"""

    __tablename__ = "politiker"

    id: Mapped[uuid.UUID] = _pk()
    partei_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parteien.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    amt: Mapped[str | None] = mapped_column(Text)  # z.B. "MdB", "Landesvorsitzender"
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    partei: Mapped["Partei"] = relationship(back_populates="politiker")
    ereignisse: Mapped[list["Ereignis"]] = relationship(back_populates="politiker")
    abstimmungen: Mapped[list["Abstimmung"]] = relationship(
        back_populates="politiker", cascade="all, delete-orphan"
    )


class Quelle(Base):
    """3. quellen"""

    __tablename__ = "quellen"

    id: Mapped[uuid.UUID] = _pk()
    medienname: Mapped[str] = mapped_column(Text, nullable=False)  # z.B. "FAZ", "dpa"
    url_basis: Mapped[str | None] = mapped_column(Text)
    vertrauensstufe: Mapped[Vertrauensstufe] = mapped_column(
        _enum(Vertrauensstufe), default=Vertrauensstufe.serioes, nullable=False
    )
    # Begründung, warum eine Quelle "ausgeschlossen" ist (Kriterien 4d).
    ausschluss_begruendung: Mapped[str | None] = mapped_column(Text)

    ereignis_quellen: Mapped[list["EreignisQuelle"]] = relationship(
        back_populates="quelle"
    )


class Ereignis(Base):
    """4. ereignisse – Kern-Tabelle (Kontroversen, Amtliche Feststellungen …)."""

    __tablename__ = "ereignisse"

    id: Mapped[uuid.UUID] = _pk()
    partei_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parteien.id"), nullable=False
    )
    politiker_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("politiker.id")  # optional, falls personenbezogen
    )
    titel: Mapped[str] = mapped_column(Text, nullable=False)
    beschreibung: Mapped[str | None] = mapped_column(Text)  # neutral formuliert
    kategorie: Mapped[Ereigniskategorie] = mapped_column(
        _enum(Ereigniskategorie), nullable=False
    )
    status: Mapped[Ereignisstatus] = mapped_column(
        _enum(Ereignisstatus), default=Ereignisstatus.vorlaeufig, nullable=False
    )
    datum_ereignis: Mapped[dt.date | None] = mapped_column(Date)
    datum_erfasst: Mapped[dt.date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )
    gegendarstellung_url: Mapped[str | None] = mapped_column(Text)  # Kriterien 4a

    partei: Mapped["Partei"] = relationship(back_populates="ereignisse")
    politiker: Mapped["Politiker | None"] = relationship(back_populates="ereignisse")
    ereignis_quellen: Mapped[list["EreignisQuelle"]] = relationship(
        back_populates="ereignis", cascade="all, delete-orphan"
    )
    embedding: Mapped["EreignisEmbedding | None"] = relationship(
        back_populates="ereignis", cascade="all, delete-orphan", uselist=False
    )


class EreignisQuelle(Base):
    """5. ereignis_quellen – Verknüpfungstabelle (n:m).

    Hier wird für die 3-Quellen-Regel gezählt.
    """

    __tablename__ = "ereignis_quellen"

    id: Mapped[uuid.UUID] = _pk()
    ereignis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ereignisse.id", ondelete="CASCADE"), nullable=False
    )
    quelle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quellen.id"), nullable=False
    )
    artikel_url: Mapped[str] = mapped_column(Text, nullable=False)
    artikel_titel: Mapped[str | None] = mapped_column(Text)
    erfasst_am: Mapped[dt.date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )

    ereignis: Mapped["Ereignis"] = relationship(back_populates="ereignis_quellen")
    quelle: Mapped["Quelle"] = relationship(back_populates="ereignis_quellen")
    snapshots: Mapped[list["ArtikelSnapshot"]] = relationship(
        back_populates="ereignis_quelle", cascade="all, delete-orphan"
    )


class ArtikelSnapshot(Base):
    """6. artikel_snapshots – Diff-Tracking (Alleinstellungsmerkmal)."""

    __tablename__ = "artikel_snapshots"

    id: Mapped[uuid.UUID] = _pk()
    ereignis_quelle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ereignis_quellen.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_datum: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(Text)  # Hash des Haupttexts
    wayback_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SnapshotStatus] = mapped_column(
        _enum(SnapshotStatus), default=SnapshotStatus.original, nullable=False
    )
    geprueft_von: Mapped[str | None] = mapped_column(Text)  # manuelle Prüfung, wer/wann

    ereignis_quelle: Mapped["EreignisQuelle"] = relationship(
        back_populates="snapshots"
    )


class Abstimmung(Base):
    """7. abstimmungen – aus Bundestag Open Data."""

    __tablename__ = "abstimmungen"

    id: Mapped[uuid.UUID] = _pk()
    politiker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("politiker.id", ondelete="CASCADE"), nullable=False
    )
    thema: Mapped[str] = mapped_column(Text, nullable=False)
    datum: Mapped[dt.date | None] = mapped_column(Date)
    stimme: Mapped[Stimme] = mapped_column(_enum(Stimme), nullable=False)
    quelle_url: Mapped[str | None] = mapped_column(Text)  # Original-Protokoll

    politiker: Mapped["Politiker"] = relationship(back_populates="abstimmungen")


class NutzerFrage(Base):
    """8. nutzer_fragen – "wurde das schon besprochen?" (RAG, pgvector)."""

    __tablename__ = "nutzer_fragen"

    id: Mapped[uuid.UUID] = _pk()
    frage_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)
    verknuepftes_ereignis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ereignisse.id")
    )
    gestellt_am: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    aehnliche_fragen_gefunden: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )


class EreignisEmbedding(Base):
    """Vektor-Tabelle für die RAG-Frage-Funktion (Datenmodell, Schluss-Notiz).

    Speichert Embeddings von ``ereignisse.beschreibung`` +
    ``ereignis_quellen.artikel_titel``, verknüpft per ``ereignis_id``,
    damit Antworten immer auf konkrete Ereignis-Datensätze zurückverlinken
    (Zitations-Pflicht).
    """

    __tablename__ = "ereignis_embeddings"

    ereignis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ereignisse.id", ondelete="CASCADE"), primary_key=True
    )
    quelltext: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=False)
    aktualisiert_am: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ereignis: Mapped["Ereignis"] = relationship(back_populates="embedding")


class PositionsHistorie(Base):
    """9. positions_historie – Programm-Änderungen über Zeit."""

    __tablename__ = "positions_historie"

    id: Mapped[uuid.UUID] = _pk()
    partei_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parteien.id", ondelete="CASCADE"), nullable=False
    )
    thema: Mapped[str] = mapped_column(Text, nullable=False)  # z.B. "Rentenpolitik"
    position_alt: Mapped[str | None] = mapped_column(Text)
    position_neu: Mapped[str | None] = mapped_column(Text)
    geaendert_am: Mapped[dt.date | None] = mapped_column(Date)
    quelle_url: Mapped[str | None] = mapped_column(Text)  # Beleg für die Änderung

    partei: Mapped["Partei"] = relationship(back_populates="positionen")


class MethodikChangelog(Base):
    """10. methodik_changelog – Transparenz-Pflicht (Kriterien Punkt 6)."""

    __tablename__ = "methodik_changelog"

    id: Mapped[uuid.UUID] = _pk()
    datum: Mapped[dt.date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )
    was_geaendert: Mapped[str] = mapped_column(Text, nullable=False)
    warum: Mapped[str | None] = mapped_column(Text)


class Meldung(Base):
    """12. meldungen – Nachrichten-Aggregation (Konzept 3.2).

    Aggregierte Artikel seriöser Medien. ``inhalt_hash`` dient der exakten
    Duplikat-Erkennung, ``cluster_id`` gruppiert Near-Duplicates derselben
    Story über verschiedene Quellen (Grundlage für den Framing-Vergleich).
    """

    __tablename__ = "meldungen"

    id: Mapped[uuid.UUID] = _pk()
    quelle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quellen.id"), nullable=False
    )
    partei_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parteien.id"))
    titel: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    zusammenfassung: Mapped[str | None] = mapped_column(Text)
    veroeffentlicht_am: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    erfasst_am: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    inhalt_hash: Mapped[str | None] = mapped_column(Text, index=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True
    )
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)

    quelle: Mapped["Quelle"] = relationship()
    partei: Mapped["Partei | None"] = relationship()
    erwaehnungen: Mapped[list["Erwaehnung"]] = relationship(
        back_populates="meldung", cascade="all, delete-orphan"
    )


class Erwaehnung(Base):
    """13. erwaehnungen – NER-Tagging (Tech-Ansatz 6).

    Verknüpft eine Meldung (oder ein Ereignis) mit erkannten Politikern/
    Parteien. ``methode`` dokumentiert, wie erkannt wurde (Gazetteer/spaCy).
    """

    __tablename__ = "erwaehnungen"

    id: Mapped[uuid.UUID] = _pk()
    meldung_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meldungen.id", ondelete="CASCADE")
    )
    ereignis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ereignisse.id", ondelete="CASCADE")
    )
    politiker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("politiker.id"))
    partei_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parteien.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)  # erkannte Oberflächenform
    methode: Mapped[TagMethode] = mapped_column(
        _enum(TagMethode), default=TagMethode.gazetteer, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "politiker_id IS NOT NULL OR partei_id IS NOT NULL",
            name="ck_erwaehnung_hat_ziel",
        ),
    )

    meldung: Mapped["Meldung | None"] = relationship(back_populates="erwaehnungen")


class AuditLog(Base):
    """11. audit_log – Nachweis bei Manipulationsvorwürfen."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _pk()
    tabelle: Mapped[str] = mapped_column(Text, nullable=False)
    datensatz_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    aktion: Mapped[AuditAktion] = mapped_column(_enum(AuditAktion), nullable=False)
    datum: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    akteur: Mapped[str | None] = mapped_column(Text)  # System-Job oder manueller Eingriff


__all__ = [
    "Partei",
    "Politiker",
    "Quelle",
    "Ereignis",
    "EreignisQuelle",
    "ArtikelSnapshot",
    "Abstimmung",
    "NutzerFrage",
    "EreignisEmbedding",
    "PositionsHistorie",
    "MethodikChangelog",
    "AuditLog",
    "Meldung",
    "Erwaehnung",
]
