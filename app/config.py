"""Zentrale Konfiguration, aus Umgebungsvariablen / .env geladen."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://parteiwiki:parteiwiki@localhost:5432/parteiwiki"
    )
    embedding_dim: int = 384
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
