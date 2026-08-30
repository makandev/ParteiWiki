"""Importiert Politiker einer Partei von abgeordnetenwatch.de.

Aufruf:  python -m scripts.import_politicians "AfD" --party-id 1 [--limit 200]

Die abgeordnetenwatch-Partei-ID (--party-id) entnimmt man einmalig der API
(GET /api/v2/parties). Ohne --party-id werden alle Politiker der ersten Seite
abgerufen und nur die der genannten Partei zugeordneten importiert.
"""
from __future__ import annotations

import argparse

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Partei
from app.services.abgeordnetenwatch import AbgeordnetenwatchClient, import_politicians


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("partei_name")
    ap.add_argument("--party-id", type=int, default=None)
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        partei = db.scalar(select(Partei).where(Partei.name == args.partei_name))
        if partei is None:
            print(f"Partei '{args.partei_name}' nicht gefunden. Erst anlegen/seed.")
            return
        client = AbgeordnetenwatchClient()
        try:
            rohdaten = client.politicians(party_id=args.party_id, limit=args.limit)
        except httpx.HTTPError as exc:
            print(f"Abruf fehlgeschlagen (Netz/Egress?): {exc}")
            return
        finally:
            client.close()
        neu = import_politicians(db, partei, rohdaten)
        db.commit()
        print(f"{neu} neue Politiker für '{partei.name}' importiert "
              f"(von {len(rohdaten)} abgerufenen).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
