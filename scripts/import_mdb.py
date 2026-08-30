"""Importiert echte Bundestags-MdBs (alle Parteien) von abgeordnetenwatch.de.

Aufruf:  python -m scripts.import_mdb --period <PARLIAMENT_PERIOD_ID> [--limit 1000]

Die --period-ID ist die abgeordnetenwatch-ID der Bundestags-Legislaturperiode.
Sie ermittelt man einmalig über die API:
    GET /api/v2/parliament-periods?parliament[entity.label]=Bundestag&type=legislature
und nimmt die aktuelle Periode. Alle Mandate dieser Periode werden abgerufen und
je Partei den passenden Datensätzen zugeordnet (Normalisierung der Parteilabels).
Parteien ohne passenden Datensatz werden übersprungen (gleiche Methodik für alle).

Hinweis: In dieser Ausführungsumgebung ist der Netzabruf per Egress-Policy
gesperrt; das Skript ist für Umgebungen mit Netzzugang gedacht. Parsing/Import
sind über Fixtures getestet (tests/test_import_mdb.py).
"""
from __future__ import annotations

import argparse

import httpx

from app.database import SessionLocal
from app.services.abgeordnetenwatch import AbgeordnetenwatchClient, import_mdb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", type=int, required=True,
                    help="abgeordnetenwatch parliament_period-ID (Bundestag).")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        client = AbgeordnetenwatchClient()
        try:
            mandate = client.mandate(parliament_period=args.period, limit=args.limit)
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
