"""News-Aggregation und NER-Tagging: meldungen + erwaehnungen.

Revision ID: 0002_news_ner
Revises: 0001_initial
Create Date: 2025-01-02

Erzeugt die beiden neuen Tabellen direkt aus ihren ORM-Definitionen, damit
Vector-Spalten, Enums, Indizes und Constraints ohne Drift übernommen werden.
"""
from alembic import op

from app.models import Erwaehnung, Meldung

revision = "0002_news_ner"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Meldung.__table__.create(bind=bind)
    Erwaehnung.__table__.create(bind=bind)  # referenziert meldungen


def downgrade() -> None:
    bind = op.get_bind()
    Erwaehnung.__table__.drop(bind=bind)
    Meldung.__table__.drop(bind=bind)
