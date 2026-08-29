"""Embedding-Layer für die RAG-Frage-Funktion (Konzept 3.3 / 6).

Dies ist bewusst ein *Gerüst*: Der Standard-Embedder (``HashingEmbedder``)
läuft vollständig offline und deterministisch, ohne API-Schlüssel oder
Modell-Download – ideal für Entwicklung, Tests und den Pilot. Für den
Produktivbetrieb wird an derselben Stelle ein echtes multilinguales Modell
(z. B. sentence-transformers ``paraphrase-multilingual-MiniLM-L12-v2``)
eingehängt, indem ``get_embedder`` eine andere Implementierung zurückgibt.

Wichtig bleibt in beiden Fällen die Zitations-Pflicht: Ergebnisse verweisen
über ``ereignis_id`` immer auf konkrete Ereignis-Datensätze.
"""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

from app.config import settings


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]:
        ...


class HashingEmbedder:
    """Deterministisches, offline lauffähiges Platzhalter-Embedding.

    Bildet Tokens per Hashing-Trick auf einen Vektor fester Dimension ab und
    normalisiert ihn (L2). Erfasst grobe lexikalische Ähnlichkeit – genug, um
    die RAG-Pipeline End-to-End zu betreiben, aber kein Ersatz für ein echtes
    Sprachmodell im Produktivbetrieb.
    """

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or settings.embedding_dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = [t for t in _tokenize(text) if t]
        for tok in tokens:
            h = hashlib.sha1(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


def _tokenize(text: str) -> list[str]:
    return "".join(c.lower() if c.isalnum() else " " for c in text).split()


class SentenceTransformerEmbedder:
    """Echtes multilinguales Embedding via sentence-transformers.

    Wird nur genutzt, wenn ``EMBEDDER=sbert`` gesetzt UND das Paket samt Modell
    verfügbar ist. Das Standardmodell hat 384 Dimensionen und passt damit zur
    ``embedding_dim``-Spaltenbreite; bei Modellwechsel ``EMBEDDING_DIM``
    entsprechend anpassen und neu indexieren.
    """

    def __init__(self, modell: str, dim: int):
        from sentence_transformers import SentenceTransformer  # lazy import

        self._model = SentenceTransformer(modell)
        self.dim = self._model.get_sentence_embedding_dimension()
        if self.dim != dim:
            raise ValueError(
                f"EMBEDDING_DIM={dim} passt nicht zum Modell ({self.dim} Dim.)"
            )

    def embed(self, text: str) -> list[float]:
        vec = self._model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vec]


class SpacyVectorEmbedder:
    """Echte semantische Embeddings aus spaCy-Wortvektoren (offline).

    Nutzt ein spaCy-Modell MIT Vektoren (z. B. ``de_core_news_md`` = 300 Dim).
    Der Dokumentvektor ist das (von spaCy gemittelte) Wortvektor-Mittel,
    anschließend L2-normalisiert. Funktioniert vollständig ohne externe Dienste
    und ist damit auch dort einsetzbar, wo Modell-Hubs gesperrt sind.
    """

    def __init__(self, modell: str, dim: int):
        import numpy as np  # lazy

        from app.core.spacy_loader import load_spacy

        self._np = np
        self._nlp = load_spacy(modell)  # geteilte Instanz (auch vom NER genutzt)
        if not self._nlp.vocab.vectors_length:
            raise ValueError(f"spaCy-Modell '{modell}' hat keine Wortvektoren.")
        self.dim = self._nlp.vocab.vectors_length
        if self.dim != dim:
            raise ValueError(
                f"EMBEDDING_DIM={dim} passt nicht zum Modell ({self.dim} Dim.)"
            )
        # Fallback für Texte ganz ohne bekannte Wortvektoren (Nullvektor -> NaN
        # bei cosine_distance). Deterministisch, gleiche Dimension.
        self._fallback = HashingEmbedder(self.dim)

    def embed(self, text: str) -> list[float]:
        # make_doc tokenisiert nur (ohne Pipeline-Komponenten) – der .vector
        # kommt aus der statischen Vektortabelle, also schnell trotz geteiltem
        # Voll-Modell.
        vec = self._nlp.make_doc(text or "").vector
        norm = float(self._np.linalg.norm(vec))
        if norm == 0:
            # Kein einziges Vektorwort erkannt -> deterministischer Fallback,
            # damit die Zeile nie einen Nullvektor (NaN-Distanz) speichert.
            return self._fallback.embed(text)
        return [float(x) for x in (vec / norm)]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Singleton-Zugriff auf den aktiven Embedder (per Konfiguration wählbar)."""
    global _embedder
    if _embedder is not None:
        return _embedder
    backend = settings.embedder.lower()
    try:
        if backend == "sbert":
            _embedder = SentenceTransformerEmbedder(
                settings.embedding_model, settings.embedding_dim
            )
            return _embedder
        if backend in ("spacy", "spacy_vectors"):
            _embedder = SpacyVectorEmbedder(settings.spacy_model, settings.embedding_dim)
            return _embedder
    except Exception as exc:  # pragma: no cover - abhängig von Installation
        print(f"[embeddings] Backend '{backend}' nicht verfügbar ({exc}) – Fallback auf hashing.")
    _embedder = HashingEmbedder()
    return _embedder
