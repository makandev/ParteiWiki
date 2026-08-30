"""Importiert die jüngste Sonntagsfrage (DAWUM) als Umfrage-Kennzahlen.

Aufruf:  python -m scripts.import_umfragen

Ordnet die aktuelle Bundestags-Umfrage je Partei zu (nur aktueller Stand,
quellenpflichtig). Auf dem Server läuft der Abgleich automatisch beim Start und
im Ingestion-Intervall; dieses Skript ist für den manuellen Anstoß.

Hinweis: In dieser Bau-Umgebung ist der Netzabruf per Egress-Policy gesperrt;
das Skript ist für Umgebungen mit Netzzugang gedacht. Parsing/Import sind über
Fixtures getestet (tests/test_dawum.py).
"""
from __future__ import annotations

import httpx

from app.database import SessionLocal
from app.services.umfrage_sync import sync_umfragen


def main() -> None:
    db = SessionLocal()
    try:
        ergebnis = sync_umfragen(db)
        print(f"Umfrage-Import: {ergebnis}")
    except httpx.HTTPError as exc:
        print(f"Abruf fehlgeschlagen (Netz/Egress?): {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
