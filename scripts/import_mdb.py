"""Importiert echte Bundestags-MdBs (alle Parteien) von abgeordnetenwatch.de.

Aufruf:  python -m scripts.import_mdb            # aktuelle Periode automatisch
         python -m scripts.import_mdb --period <ID> [--limit 1000]

Ohne --period ermittelt das Skript die aktuelle Bundestags-Legislaturperiode
selbst. Alle Mandate dieser Periode werden abgerufen und je Partei den
passenden Datensätzen zugeordnet (Normalisierung der Parteilabels). Parteien
ohne passenden Datensatz werden übersprungen (gleiche Methodik für alle);
Re-Läufe sind idempotent.

Hinweis: In dieser Bau-Umgebung ist der Netzabruf per Egress-Policy gesperrt;
das Skript ist für Umgebungen mit Netzzugang gedacht (z. B. der Server). Auf
dem Server läuft der Abgleich zudem automatisch beim Start (MDB_SYNC_BEIM_START).
Parsing/Import/Perioden-Auswahl sind über Fixtures getestet.
"""
from __future__ import annotations

import argparse

import httpx

from app.database import SessionLocal
from app.services.abgeordnetenwatch import AbgeordnetenwatchClient, import_mdb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", type=int, default=None,
                    help="abgeordnetenwatch parliament_period-ID (Bundestag). "
                         "Weglassen = aktuelle Periode automatisch wählen.")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        client = AbgeordnetenwatchClient()
        try:
            period = args.period
            if period is None:
                periode = client.aktuelle_bundestag_periode()
                if periode is None or periode.externe_id is None:
                    print("Keine aktuelle Bundestags-Periode gefunden.")
                    return
                period = periode.externe_id
                print(f"Aktuelle Periode: {periode.label or period} (ID {period}).")
            mandate = client.mandate(parliament_period=period, limit=args.limit)
        except httpx.HTTPError as exc:
            print(f"Abruf fehlgeschlagen (Netz/Egress?): {exc}")
            return
        finally:
            client.close()
        ergebnis = import_mdb(db, mandate)
        db.commit()
        uebersprungen = ergebnis.pop("_uebersprungen", 0)
        gesamt = sum(ergebnis.values())
        print(f"{gesamt} neue MdBs importiert (von {len(mandate)} Mandaten, "
              f"{uebersprungen} übersprungen).")
        for name in sorted(ergebnis):
            print(f"  {name}: {ergebnis[name]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
