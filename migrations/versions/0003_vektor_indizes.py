"""HNSW-Indizes für die Vektor-Spalten (ANN-Suche statt Seq-Scan).

Revision ID: 0003_vektor_indizes
Revises: 0002_news_ner
Create Date: 2025-01-03

Alle Ähnlichkeitssuchen nutzen die Cosinus-Distanz, daher die Operatorklasse
``vector_cosine_ops``. Betrifft die drei Embedding-Spalten (Ereignisse,
Nutzerfragen, Meldungen).
"""
from alembic import op

revision = "0003_vektor_indizes"
down_revision = "0002_news_ner"
branch_labels = None
depends_on = None

_INDIZES = [
    ("ix_ereignis_embeddings_vec", "ereignis_embeddings"),
    ("ix_nutzer_fragen_vec", "nutzer_fragen"),
    ("ix_meldungen_vec", "meldungen"),
]


def upgrade() -> None:
    for name, tabelle in _INDIZES:
        op.execute(
            f"CREATE INDEX {name} ON {tabelle} "
            f"USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    for name, _ in _INDIZES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
