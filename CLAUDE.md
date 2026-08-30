# CLAUDE.md – Projektleitfaden für ParteiWiki

Neutrale, quellenbasierte Wissensplattform pro Partei (Konzepte: App-Konzept,
Datenmodell, redaktionelle Kriterien). Grundprinzip: **gleiche Methodik für
jede Partei, keine eigene Bewertung, keine Behauptung ohne Quelle.**

## Stack
- Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Postgres + `pgvector`.
- Server-gerenderte Web-Views (Jinja2) + REST-API unter `/api`.
- Echte semantische Embeddings über spaCy-Wortvektoren; spaCy-Hybrid-NER;
  belegpflichtiger LLM-Layer (extraktiv per Default, Anthropic-SDK optional).

## Befehle
```bash
pip install -r requirements.txt
python -m spacy download de_core_news_md   # echtes NER + Embeddings (300 Dim)
cp .env.example .env
docker compose up -d                       # Postgres + pgvector
alembic upgrade head                       # Schema (0001–0003)
python -m scripts.seed                      # Pilot-Daten (AfD)
uvicorn app.main:app --reload
pytest                                      # Unit-Tests; DB-Tests laufen bei erreichbarer DB
```
Ingestion/Jobs: `scripts.ingest_news`, `scripts.check_diffs`, `scripts.reindex`,
`scripts.import_politicians`, `scripts.import_votes`, `scripts.import_mdb`
(echte Abgeordnete), `scripts.import_umfragen` (DAWUM-Sonntagsfrage),
`scripts.seed_kennzahlen` (Wahlergebnisse). MdB-/Umfrage-Abgleich läuft auf dem
Server zusätzlich automatisch (Start-Job + Intervall).

## Architektur (Kurz)
- `app/models/` – ORM 1:1 zum Datenmodell + `meldungen`/`erwaehnungen`.
- `app/enums.py` – Kategorien/Status/Vertrauensstufen der Kriterien.
- `app/core/` – `neutralitaet` (3-Quellen-Regel), `audit`, `embeddings`, `ner`,
  `llm`, `spacy_loader` (gecachtes, geteiltes spaCy-Modell).
- `app/services/` – `news`, `diff_tracking`, `rag`, `abgeordnetenwatch`, `bundestag`,
  `mandate_sync` (MdBs), `dawum`/`umfrage_sync` (Umfragen), `partei_stats` (Aggregate).
- `app/api/` – Router; `app/web/` – Views + neutrale Labels (Vergleich, Medien, Kennzahlen).
- `migrations/` – 0001 Basis, 0002 news/ner, 0003 HNSW-Vektor-Indizes,
  0004 quellen.spektrum, 0005 kennzahlen (Zahlen über Zeit, quellenpflichtig).

## Konventionen
- Deutschsprachige Bezeichner/Docstrings (Domänensprache der Konzepte).
- Redaktionelle Regeln gehören ins Datenmodell/`app/core/neutralitaet.py`,
  nicht in Ad-hoc-Code – sie gelten für alle Parteien gleich.
- Schwere Backends (spaCy, sbert, Anthropic) hinter Interfaces mit Fallback;
  Default muss offline lauffähig bleiben. Vektor-Dimension (`EMBEDDING_DIM`)
  muss zum aktiven Embedder passen (spaCy md = 300, sbert = 384).
- Jede Schreiboperation über `app/core/audit.py` protokollieren.
- Änderungen an der Methodik im `methodik_changelog` dokumentieren (Transparenz).

## Tests
- Unit-Tests sind DB-frei und laufen überall.
- `tests/conftest.py` überspringt DB-Integrationstests, wenn keine DB erreichbar
  ist, und erzwingt für Tests die leichten Backends (Hashing/Gazetteer).
- Vor Commit: `pytest` grün halten; bei DB-nahen Änderungen mit laufender DB testen.

## Umgebungshinweis
Externe Hosts (HuggingFace-Modell-Hub, RSS/abgeordnetenwatch/Bundestag) sind in
der Cloud-Ausführungsumgebung per Egress-Policy gesperrt. Der scharfe Default
nutzt daher spaCy-Vektoren; sbert/externe Ingestion greifen in Umgebungen mit
Netzzugang.
