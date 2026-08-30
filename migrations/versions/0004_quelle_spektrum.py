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


def _hat_spalte(bind, tabelle: str, spalte: str) -> bool:
    return spalte in {c["name"] for c in sa.inspect(bind).get_columns(tabelle)}


def upgrade() -> None:
    # Idempotent: Das Basis-Schema (0001) legt Tabellen aus dem aktuellen Modell
    # an – auf einer frisch aufgesetzten DB existiert die Spalte daher evtl.
    # schon. Nur ergänzen, wenn sie fehlt (bestehende DBs migrieren normal).
    bind = op.get_bind()
    if not _hat_spalte(bind, "quellen", "spektrum"):
        op.add_column("quellen", sa.Column("spektrum", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _hat_spalte(bind, "quellen", "spektrum"):
        op.drop_column("quellen", "spektrum")
