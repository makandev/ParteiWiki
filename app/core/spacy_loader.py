"""Zentrales, gecachtes Laden von spaCy-Modellen.

Sowohl der NER-Tagger als auch der Wortvektor-Embedder brauchen dasselbe
deutsche Modell. Über den ``lru_cache`` wird es genau einmal pro Prozess in den
Speicher geladen, statt mehrfach.

Nebenläufigkeit: Die geteilte ``Language``-Instanz wird auf dem Web-Pfad nur
lesend genutzt (``make_doc`` + statische Vektoren beim Embedden). Die volle
NER-Pipeline (``nlp(text)``) läuft ausschließlich in der Single-Thread-
Ingestion (Skripte), nicht im FastAPI-Threadpool – daher kein Pipeline-Zustand,
der zwischen Request-Threads konkurriert.
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=4)
def load_spacy(modell: str):
    """Lädt ein spaCy-Modell (gecacht). Wirft, wenn nicht installiert."""
    import spacy

    return spacy.load(modell)
