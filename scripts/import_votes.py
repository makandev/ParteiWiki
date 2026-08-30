"""Importiert eine namentliche Abstimmung (Bundestag Open Data) aus einer XML-Datei.

Die Dateien lädt man je Abstimmung von bundestag.de/services/opendata herunter.

Aufruf:  python -m scripts.import_votes pfad/zur/abstimmung.xml [--quelle-url URL]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.database import SessionLocal
from app.services.bundestag import import_abstimmungen, parse_namentliche_abstimmung


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xml_pfad")
    ap.add_argument("--quelle-url", default="https://www.bundestag.de/services/opendata")
    args = ap.parse_args()

    inhalt = Path(args.xml_pfad).read_bytes()
    meta = parse_namentliche_abstimmung(inhalt)
    print(f"Abstimmung: {meta.thema!r} ({meta.datum}), {len(meta.saetze)} Stimmen im Dokument.")

    db = SessionLocal()
    try:
        importiert = import_abstimmungen(db, meta, quelle_url=args.quelle_url)
        db.commit()
        print(f"{importiert} Stimmen bekannten Politikern zugeordnet und importiert.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
