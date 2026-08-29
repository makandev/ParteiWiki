"""Initiales Schema: Tabellen des Datenmodell-Entwurfs + pgvector.

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01

Legt genau die zu dieser Revision gehörenden Tabellen an – explizit
aufgezählt, damit spätere Modell-Ergänzungen (z. B. meldungen/erwaehnungen
in 0002) diese Migration nicht rückwirkend verändern. Voraussetzung ist die
pgvector-Extension, die hier zuerst erzeugt wird.
"""
from alembic import op

from app.database import Base
from app.models import (
    Abstimmung,
    ArtikelSnapshot,
    AuditLog,
    Ereignis,
    EreignisEmbedding,
    EreignisQuelle,
    MethodikChangelog,
    NutzerFrage,
    Partei,
    Politiker,
    PositionsHistorie,
    Quelle,
)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Reihenfolge unerheblich – create_all/drop_all sortiert nach Abhängigkeiten.
_MODELLE = (
    Partei,
    Politiker,
    Quelle,
    Ereignis,
    EreignisQuelle,
    ArtikelSnapshot,
    Abstimmung,
    NutzerFrage,
    EreignisEmbedding,
    PositionsHistorie,
    MethodikChangelog,
    AuditLog,
)


def _tabellen():
    return [m.__table__ for m in _MODELLE]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind(), tables=_tabellen())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), tables=_tabellen())
