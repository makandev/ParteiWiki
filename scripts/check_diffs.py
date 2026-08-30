"""Cronjob-Einstiegspunkt für das Diff-Tracking.

Prüft alle erfassten Artikel-URLs gegen Wayback-Snapshots und legt bei
Änderungen/Löschungen neue Snapshots an (Status zunächst "möglicherweise
verändert" bis zur manuellen Prüfung).

Beispiel-Cron (täglich 03:00):
    0 3 * * *  cd /pfad/zu/ParteiWiki && python -m scripts.check_diffs
"""
from __future__ import annotations

from app.database import SessionLocal
from app.services.diff_tracking import pruefe_alle


def main() -> None:
    db = SessionLocal()
    try:
        anzahl = pruefe_alle(db)
        print(f"Diff-Tracking abgeschlossen: {anzahl} neue Snapshot(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
