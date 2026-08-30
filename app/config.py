"""Zentrale Konfiguration, aus Umgebungsvariablen / .env geladen."""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://parteiwiki:parteiwiki@localhost:5432/parteiwiki"
    )

    @field_validator("database_url")
    @classmethod
    def _db_url_dialekt(cls, v: str) -> str:
        """Normalisiert die DB-URL auf das SQLAlchemy-Dialekt-Präfix.

        Hoster wie Fly.io/Heroku injizieren ``postgres://`` bzw. ``postgresql://``;
        SQLAlchemy 2.0 lehnt beides ab und braucht ``postgresql+psycopg://``.
        Ein bereits gesetztes ``+treiber``-Präfix bleibt unangetastet.
        """
        if v.startswith("postgresql+"):
            return v
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v
    # Vektor-Dimension. Muss zum aktiven Embedder passen:
    #   spacy_vectors (de_core_news_md) = 300, sbert (MiniLM) = 384, hashing = frei.
    embedding_dim: int = 300
    # Embedder-Backend: "spacy_vectors" (echte Wortvektoren, offline),
    # "sbert" (Transformer, benötigt Modell-Hub) oder "hashing" (ohne Modell).
    embedder: str = "spacy_vectors"
    # Für "sbert": multilinguales Modell mit 384 Dimensionen.
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    # NER-Backend: "spacy" (Hybrid mit Gazetteer) oder "gazetteer" (ohne Modell).
    ner: str = "spacy"
    # spaCy-Modell MIT Wortvektoren (für NER und spacy_vectors-Embeddings).
    spacy_model: str = "de_core_news_md"
    # LLM-Layer für die Antwortsynthese: "extractive" (offline, deterministisch)
    # oder "anthropic" (offizielles SDK, benötigt Anmeldedaten). Beide zitieren.
    llm: str = "extractive"
    llm_model: str = "claude-opus-5"
    wayback_api: str = "https://archive.org/wayback/available"

    # Redaktionelle Kriterien, Punkt 1: 3-Quellen-Regel.
    bestaetigt_ab_quellen: int = 3

    env: str = "development"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
