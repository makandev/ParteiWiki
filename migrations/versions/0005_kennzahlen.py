"""kennzahlen – veränderliche Zahlen je Partei über die Zeit (quellenpflichtig).

Revision ID: 0005_kennzahlen
Revises: 0004_quelle_spektrum
Create Date: 2025-01-05

Wahlergebnisse, Umfragen, Sitze, Mitgliederzahlen – jeweils mit Zeitpunkt und
Pflicht-Quelle. Eindeutig je (Partei, Art, Zeitpunkt) für idempotente Importe.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_kennzahlen"
down_revision = "0004_quelle_spektrum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kennzahlen",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("partei_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("art", sa.String(), nullable=False),
        sa.Column("wert", sa.Float(), nullable=False),
        sa.Column("einheit", sa.Text(), nullable=False, server_default="%"),
        sa.Column("zeitpunkt", sa.Date(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("quelle_url", sa.Text(), nullable=False),
        sa.Column("quelle_name", sa.Text(), nullable=True),
        sa.Column("vorlaeufig", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bemerkung", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["partei_id"], ["parteien.id"], ondelete="CASCADE"),
        sa.CheckConstraint("quelle_url <> ''", name="ck_kennzahl_hat_quelle"),
    )
    op.create_index(
        "ix_kennzahlen_partei_art_zeit",
        "kennzahlen",
        ["partei_id", "art", "zeitpunkt"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_kennzahlen_partei_art_zeit", table_name="kennzahlen")
    op.drop_table("kennzahlen")
