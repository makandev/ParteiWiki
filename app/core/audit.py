"""Audit-Log – Nachweis bei Manipulationsvorwürfen (Konzept, Punkt 6 / Tabelle 11).

Jede schreibende Operation soll hierüber protokolliert werden: wer/was/wann.
Der Aufruf hängt einen ``AuditLog``-Eintrag an die Session an; das Commit
erfolgt gemeinsam mit der eigentlichen Änderung durch den Aufrufer.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.enums import AuditAktion
from app.models import AuditLog


def audit(
    db: Session,
    *,
    tabelle: str,
    datensatz_id: uuid.UUID | None,
    aktion: AuditAktion,
    akteur: str = "system",
) -> AuditLog:
    """Protokolliert eine Änderung. Kein Commit – das übernimmt der Aufrufer."""
    eintrag = AuditLog(
        tabelle=tabelle,
        datensatz_id=datensatz_id,
        aktion=aktion,
        akteur=akteur,
    )
    db.add(eintrag)
    return eintrag
