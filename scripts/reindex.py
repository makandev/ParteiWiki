"""Baut den RAG-Vektor-Index über alle Ereignisse neu auf.

Aufruf:  python -m scripts.reindex
"""
from __future__ import annotations

from app.database import SessionLocal
from app.services.rag import reindex_alle


def main() -> None:
    db = SessionLocal()
    try:
        anzahl = reindex_alle(db)
        print(f"Reindex abgeschlossen: {anzahl} Ereignis(se) indexiert.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
