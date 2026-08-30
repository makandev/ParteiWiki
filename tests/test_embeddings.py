"""Tests des Offline-Embedders für die RAG-Pipeline."""
from __future__ import annotations

import math

from app.core.embeddings import HashingEmbedder


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_dimension_und_normierung():
    emb = HashingEmbedder(dim=64)
    v = emb.embed("Rentenpolitik der Partei")
    assert len(v) == 64
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)


def test_deterministisch():
    emb = HashingEmbedder(dim=64)
    assert emb.embed("gleicher Text") == emb.embed("gleicher Text")


def test_aehnlichkeit():
    emb = HashingEmbedder(dim=256)
    basis = emb.embed("Position zur Rentenpolitik geändert")
    nah = emb.embed("Rentenpolitik Position geändert")
    fern = emb.embed("völlig anderes Thema Fußball Wetter")
    assert _cos(basis, nah) > _cos(basis, fern)


def test_hashing_leerer_text_nie_nullvektor():
    # Auch leerer/nur-Satzzeichen-Text ergibt einen Einheitsvektor (Norm 1),
    # nie einen Nullvektor – sonst würde cosine_distance NaN liefern und die
    # Ähnlichkeitssuche verfälschen.
    for text in ("", "   ", "!!!"):
        v = HashingEmbedder(dim=32).embed(text)
        assert len(v) == 32
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)
