"""quellen.spektrum – politische Orientierung je Medium (Transparenz).

Revision ID: 0004_quelle_spektrum
Revises: 0003_vektor_indizes
Create Date: 2025-01-04

Freitext (links | mitte-links | mitte | mitte-rechts | rechts | agentur | null),
damit die App pro Quelle einen neutralen Orientierungs-Hinweis anzeigen kann.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_quelle_spektrum"
down_revision = "0003_vektor_indizes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quellen", sa.Column("spektrum", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("quellen", "spektrum")
