"""NER-Tagging von Politikern/Parteien (Tech-Ansatz Punkt 6).

Zwei Backends hinter einem gemeinsamen Interface:

* ``GazetteerTagger`` (Default) – gleicht Text gegen die in der DB bekannten
  Politiker- und Partei-Namen ab. Läuft offline, deterministisch, keine
  Modelle nötig. Bewusst konservativ (Wortgrenzen, volle Namen + kuratierte
  Aliase), um Fehlzuordnungen zu vermeiden.
* ``SpacyTagger`` (optional) – nutzt ein deutsches spaCy-Modell für PER/ORG
  und verknüpft die Funde über den Gazetteer mit konkreten Datensätzen.
  Wird nur aktiv, wenn spaCy + Modell installiert sind; sonst Fallback.

Beide erzeugen ``Erkennung``-Objekte, die auf ``politiker_id`` und/oder
``partei_id`` verweisen – nie freischwebende Entitäten ohne Ziel.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import TagMethode
from app.models import Erwaehnung, Meldung, Partei, Politiker

# Kuratierte Partei-Aliase (erweiterbar). Schlüssel = exakter Parteiname.
PARTEI_ALIASE: dict[str, list[str]] = {
    "AfD": ["Alternative für Deutschland"],
    "CDU": ["Christlich Demokratische Union"],
    "CSU": ["Christlich-Soziale Union"],
    "SPD": ["Sozialdemokratische Partei Deutschlands"],
    "FDP": ["Freie Demokratische Partei", "Freie Demokraten"],
    "Grüne": ["Bündnis 90/Die Grünen", "Bündnis 90", "Die Grünen"],
    "Die Linke": ["Linkspartei", "Die Linke"],
}

# Nachnamen, die zugleich gängige Wörter/Vornamen sind, werden NICHT als
# Nachnamen-Muster zugelassen (Falsch-Positiv-Schutz für Kriterium 1.3).
NACHNAME_STOPP: set[str] = {
    "wolf", "koch", "bauer", "richter", "jung", "lang", "kurz", "gut", "neu",
    "klein", "groß", "gross", "weiß", "weiss", "berg", "stein", "winter",
    "sommer", "herbst", "fuchs", "vogel", "stark", "roth", "braun", "schwarz",
    "hahn", "beck", "ernst", "list", "reich", "engel", "kaiser",
}


class Tagger(Protocol):
    """Gemeinsames Interface von GazetteerTagger und SpacyTagger."""

    @property
    def methode(self) -> TagMethode: ...

    def tag(self, text: str) -> list["Erkennung"]: ...


@dataclass(frozen=True)
class Erkennung:
    text: str
    politiker_id: uuid.UUID | None = None
    partei_id: uuid.UUID | None = None


@dataclass
class _Eintrag:
    muster: re.Pattern
    canonical: str
    politiker_id: uuid.UUID | None
    partei_id: uuid.UUID | None
    laenge: int


def _muster(name: str) -> re.Pattern:
    # Wortgrenzen, Unicode-fähig (Umlaute sind Wortzeichen bei str-Patterns).
    return re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)


def nachnamen_eintraege(politiker: list) -> list["_Eintrag"]:
    """Zusätzliche Nachnamen-Muster – konservativ gegen Falsch-Positive.

    Ein Nachname wird nur zugelassen, wenn er (a) unter den übergebenen
    Politikern eindeutig ist, (b) mindestens 4 Zeichen hat und (c) kein
    gängiges Wort/Vorname (``NACHNAME_STOPP``) ist. Erwartet Objekte mit
    ``name``, ``id`` und ``partei_id``.
    """
    nach: dict[str, list] = {}
    for pol in politiker:
        teile = (pol.name or "").split()
        if len(teile) >= 2:
            nach.setdefault(teile[-1], []).append(pol)
    eintraege: list[_Eintrag] = []
    for nachname, treffer in nach.items():
        if (
            len(treffer) == 1
            and len(nachname) >= 4
            and nachname.lower() not in NACHNAME_STOPP
        ):
            pol = treffer[0]
            eintraege.append(
                _Eintrag(_muster(nachname), pol.name, pol.id, pol.partei_id, len(nachname))
            )
    return eintraege


class GazetteerTagger:
    """Erkennt bekannte Namen aus der Datenbank per Wortgrenzen-Abgleich."""

    def __init__(self, eintraege: list[_Eintrag]):
        # Längere Namen zuerst prüfen ("Alice Weidel" vor "AfD").
        self._eintraege = sorted(eintraege, key=lambda e: e.laenge, reverse=True)

    @classmethod
    def aus_db(cls, db: Session) -> "GazetteerTagger":
        eintraege: list[_Eintrag] = []
        for p in db.scalars(select(Partei)).all():
            namen = [p.name, *PARTEI_ALIASE.get(p.name, [])]
            for n in namen:
                if n:
                    eintraege.append(
                        _Eintrag(_muster(n), p.name, None, p.id, len(n))
                    )
        politiker = [p for p in db.scalars(select(Politiker)).all() if p.name]
        for pol in politiker:
            eintraege.append(
                _Eintrag(_muster(pol.name), pol.name, pol.id, pol.partei_id, len(pol.name))
            )
        eintraege.extend(nachnamen_eintraege(politiker))
        return cls(eintraege)

    @property
    def methode(self) -> TagMethode:
        return TagMethode.gazetteer

    def tag(self, text: str) -> list[Erkennung]:
        if not text:
            return []
        gefunden: dict[tuple, Erkennung] = {}
        for e in self._eintraege:
            m = e.muster.search(text)
            if not m:
                continue
            schluessel = (e.politiker_id, e.partei_id)
            if schluessel not in gefunden:
                gefunden[schluessel] = Erkennung(
                    text=m.group(0),
                    politiker_id=e.politiker_id,
                    partei_id=e.partei_id,
                )
        return list(gefunden.values())


class SpacyTagger:
    """Optionales spaCy-Backend; verknüpft PER/ORG über den Gazetteer.

    Fällt still auf den reinen Gazetteer zurück, wenn spaCy/Modell fehlen.
    """

    def __init__(self, gazetteer: GazetteerTagger, modell: str = "de_core_news_sm"):
        self._gazetteer = gazetteer
        self._nlp = None
        try:  # pragma: no cover - abhängig von optionaler Installation
            from app.core.spacy_loader import load_spacy

            self._nlp = load_spacy(modell)  # geteilte Instanz (auch vom Embedder genutzt)
        except Exception:
            self._nlp = None

    @property
    def methode(self) -> TagMethode:
        return TagMethode.spacy if self._nlp is not None else TagMethode.gazetteer

    def tag(self, text: str) -> list[Erkennung]:
        if self._nlp is None:
            return self._gazetteer.tag(text)
        # Hybrid: Der Gazetteer über den ganzen Text garantiert die Trefferquote
        # bekannter Namen/Aliase unabhängig von spaCys Entity-Grenzen; spaCy
        # ergänzt kontextuelle Personen-/Org-Erwähnungen. So ist der spaCy-Modus
        # nie schlechter als der reine Gazetteer.
        treffer: list[Erkennung] = list(self._gazetteer.tag(text))  # pragma: no cover
        doc = self._nlp(text)  # pragma: no cover
        relevante = {"PER", "PERSON", "ORG", "MISC"}  # Parteien = MISC im dt. Modell
        for ent in doc.ents:  # pragma: no cover
            if ent.label_ in relevante:
                treffer.extend(self._gazetteer.tag(ent.text))
        # Dedupe über (politiker_id, partei_id).
        einzig: dict[tuple, Erkennung] = {}
        for t in treffer:  # pragma: no cover
            einzig.setdefault((t.politiker_id, t.partei_id), t)
        return list(einzig.values())


def tagger_fuer(db: Session) -> Tagger:
    """Liefert den konfigurierten Tagger (Gazetteer oder spaCy) über der DB."""
    gazetteer = GazetteerTagger.aus_db(db)
    if settings.ner.lower() == "spacy":
        return SpacyTagger(gazetteer, settings.spacy_model)
    return gazetteer


def tag_meldung(db: Session, meldung: Meldung, tagger: Tagger) -> list[Erwaehnung]:
    """Erkennt Entitäten in Titel + Zusammenfassung und legt Erwähnungen an.

    Idempotent pro (Meldung, Ziel): bestehende Erwähnungen werden nicht doppelt
    angelegt. Ohne Commit – der Aufrufer committet.
    """
    text = " ".join(filter(None, [meldung.titel, meldung.zusammenfassung]))
    erkennungen = tagger.tag(text)  # nur einmal taggen (Pipeline ist teuer)
    vorhandene = {
        (e.politiker_id, e.partei_id) for e in meldung.erwaehnungen
    }
    neu: list[Erwaehnung] = []
    for erk in erkennungen:
        schluessel = (erk.politiker_id, erk.partei_id)
        if schluessel in vorhandene:
            continue
        vorhandene.add(schluessel)
        erw = Erwaehnung(
            meldung_id=meldung.id,
            politiker_id=erk.politiker_id,
            partei_id=erk.partei_id,
            text=erk.text,
            methode=tagger.methode,
        )
        db.add(erw)
        neu.append(erw)

    # Primäre Partei der Meldung ableiten, falls noch nicht gesetzt.
    if meldung.partei_id is None:
        for erk in erkennungen:
            if erk.partei_id is not None:
                meldung.partei_id = erk.partei_id
                break
    return neu
