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


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Singleton-Zugriff auf den aktiven Embedder (per Konfiguration wählbar)."""
    global _embedder
    if _embedder is not None:
        return _embedder
    if settings.embedder.lower() == "sbert":
        try:
            _embedder = SentenceTransformerEmbedder(
                settings.embedding_model, settings.embedding_dim
            )
            return _embedder
        except Exception as exc:  # pragma: no cover - abhängig von Installation
            print(f"[embeddings] sbert nicht verfügbar ({exc}) – Fallback auf hashing.")
    _embedder = HashingEmbedder()
    return _embedder
