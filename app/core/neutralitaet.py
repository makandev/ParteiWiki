"""Redaktionelle Kriterien als Code – gilt für jede Partei gleich.

Kernregel (Kriterien Punkt 1): Ein Ereignis der Kategorie *Kontroverse* gilt
erst als ``bestaetigt``, wenn mindestens ``BESTAETIGT_AB_QUELLEN`` voneinander
unabhängige, seriöse Quellen darüber berichten. Bis dahin bleibt es als
``vorlaeufig`` sichtbar (nicht zurückgehalten).

*Amtliche Feststellungen* (Punkt 1a) unterliegen NICHT der 3-Quellen-Regel –
sie verweisen auf die Originalquelle und gelten unmittelbar als bestätigt.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.enums import Ereigniskategorie, Ereignisstatus, Vertrauensstufe
from app.models import Ereignis


def zaehle_unabhaengige_quellen(db: Session, ereignis: Ereignis) -> int:
    """Zählt distinkte, nicht ausgeschlossene Quellen eines Ereignisses.

    "Unabhängig" wird hier über distinkte ``quelle_id`` angenähert: dieselbe
    Agenturmeldung, mehrfach weiterverbreitet, zählt nur einmal, wenn sie auf
    dieselbe Quelle gemappt ist. Ausgeschlossene Quellen (Kriterien 4d) zählen
    nicht mit.
    """
    quelle_ids: set = set()
    for eq in ereignis.ereignis_quellen:
        quelle = eq.quelle
        if quelle is None:
            continue
        if quelle.vertrauensstufe == Vertrauensstufe.ausgeschlossen:
            continue
        quelle_ids.add(eq.quelle_id)
    return len(quelle_ids)


def berechne_status(db: Session, ereignis: Ereignis) -> Ereignisstatus:
    """Leitet den Status eines Ereignisses aus den Kriterien ab.

    Amtliche Feststellungen sind immer ``bestaetigt``; alle anderen Kategorien
    folgen der Quellen-Schwelle.
    """
    if ereignis.kategorie == Ereigniskategorie.amtliche_feststellung:
        return Ereignisstatus.bestaetigt

    anzahl = zaehle_unabhaengige_quellen(db, ereignis)
    if anzahl >= settings.bestaetigt_ab_quellen:
        return Ereignisstatus.bestaetigt
    return Ereignisstatus.vorlaeufig


def aktualisiere_status(db: Session, ereignis: Ereignis) -> Ereignisstatus:
    """Setzt den berechneten Status und gibt ihn zurück (ohne Commit)."""
    neu = berechne_status(db, ereignis)
    ereignis.status = neu
    return neu
