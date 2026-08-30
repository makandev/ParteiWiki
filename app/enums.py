"""Enumerationen aus dem Datenmodell- und Kriterien-Entwurf.

Die Werte kodieren die redaktionellen Kriterien direkt im Datenmodell,
damit sie für jede Partei gleich gelten (keine Sonderfälle).
"""
from __future__ import annotations

import enum


class Vertrauensstufe(str, enum.Enum):
    """quellen.vertrauensstufe – Redaktionelle Kriterien, Punkt 4d."""

    serioes = "serioes"
    mit_vorsicht = "mit_vorsicht"
    ausgeschlossen = "ausgeschlossen"


class Ereigniskategorie(str, enum.Enum):
    """ereignisse.kategorie – Kriterien Punkt 1, 1a, 2, 3.

    ``amtliche_feststellung`` unterliegt NICHT der 3-Quellen-Regel,
    sondern verweist auf die Originalquelle (Urteil, Bescheid).
    """

    kontroverse = "kontroverse"
    amtliche_feststellung = "amtliche_feststellung"
    meinung = "meinung"
    reaktion_zitat = "reaktion_zitat"


class Ereignisstatus(str, enum.Enum):
    """ereignisse.status – Kriterien Punkt 1 (3-Quellen-Regel).

    Breaking News mit nur einer Quelle bleiben ``vorlaeufig`` sichtbar
    und wechseln automatisch zu ``bestaetigt``, sobald genügend
    unabhängige Quellen vorliegen.
    """

    vorlaeufig = "vorlaeufig"
    bestaetigt = "bestaetigt"


class SnapshotStatus(str, enum.Enum):
    """artikel_snapshots.status – Kriterien Punkt 4 / 4b.

    Automatisch erkannte Änderungen sind zunächst nur
    ``moeglicherweise_veraendert`` und werden erst nach manueller
    Prüfung (Vier-Augen-Prinzip) bestätigt.
    """

    original = "original"
    moeglicherweise_veraendert = "moeglicherweise_veraendert"
    bestaetigt_veraendert = "bestaetigt_veraendert"
    entfernt = "entfernt"


class Stimme(str, enum.Enum):
    """abstimmungen.stimme – Bundestag Open Data."""

    dafuer = "dafuer"
    dagegen = "dagegen"
    enthalten = "enthalten"
    nicht_anwesend = "nicht_anwesend"


class AuditAktion(str, enum.Enum):
    """audit_log.aktion – Nachweis bei Manipulationsvorwürfen."""

    erstellt = "erstellt"
    geaendert = "geaendert"
    geloescht = "geloescht"


class Kennzahlart(str, enum.Enum):
    """kennzahlen.art – veränderliche Zahlen je Partei über die Zeit.

    Jede Kennzahl ist quellenpflichtig (gleiche Methodik für alle Parteien,
    keine Behauptung ohne Beleg). ``einheit`` (z. B. "%", "Sitze") steht
    separat im Datensatz.
    """

    bundestagswahl_zweitstimme = "bundestagswahl_zweitstimme"
    umfrage_bund = "umfrage_bund"
    sitze_bundestag = "sitze_bundestag"
    mitglieder = "mitglieder"


class TagMethode(str, enum.Enum):
    """erwaehnungen.methode – wie eine Entität erkannt wurde (Tech-Ansatz 6)."""

    gazetteer = "gazetteer"  # Abgleich gegen bekannte Namen aus der DB
    spacy = "spacy"          # spaCy-NER (optionales Backend)
    manuell = "manuell"
