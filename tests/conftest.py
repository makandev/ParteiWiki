"""Pytest-Fixtures für DB-Integrationstests.

Läuft nur, wenn eine Postgres+pgvector-DB unter ``DATABASE_URL`` erreichbar ist;
sonst werden die Integrationstests übersprungen, damit ``pytest`` in jeder
Umgebung grün bleibt. Jeder Test läuft in einer eigenen Transaktion, die am Ende
zurückgerollt wird (keine Restdaten), inkl. Endpoint-``commit()`` über Savepoints.

Für Tests werden die leichten, deterministischen Backends erzwungen
(Hashing-Embeddings, Gazetteer-NER), damit die Tests schnell und ohne
spaCy-Modell laufen. Die Vektor-Dimension bleibt beim Projekt-Default (300).
"""
from __future__ import annotations

import os

# MUSS vor dem Import von app.* gesetzt werden (Settings werden gecacht).
os.environ.setdefault("EMBEDDER", "hashing")
os.environ.setdefault("NER", "gazetteer")

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app


@pytest.fixture(scope="session")
def _db_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - Umgebungsabhängig
        pytest.skip(f"Keine DB erreichbar – Integrationstests übersprungen ({exc})")


@pytest.fixture
def db(_db_check):
    """Session in einer zurückgerollten Transaktion (Savepoint-Isolation)."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def client(db):
    """TestClient, dessen get_db-Dependency dieselbe Test-Session nutzt."""
    from fastapi.testclient import TestClient

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
