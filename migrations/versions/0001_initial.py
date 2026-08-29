"""Initiales Schema: alle Tabellen des Datenmodell-Entwurfs + pgvector.

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01

Das Schema wird direkt aus den ORM-Metadaten erzeugt, damit Modelle und
Datenbank nicht auseinanderlaufen. Voraussetzung ist die pgvector-Extension,
die hier zuerst angelegt wird.
"""
from alembic import op

from app.database import Base
import app.models  # noqa: F401  (registriert alle Tabellen in Base.metadata)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
