# ParteiWiki

Neutrale, quellenbasierte Wissensplattform pro Partei. Nutzer recherchieren,
stellen Fragen und sehen, wie sich Themen und Kontroversen über die Zeit
entwickelt haben – inklusive **Diff-Tracking** von Artikeln (was wurde
geändert oder gelöscht, was kam danach).

> **Grundprinzip (Neutralität):** Gleiche Kriterien und Methodik für **jede**
> Partei – keine Sonderfälle, keine eigene Bewertung, kein Ranking. Der Nutzer
> urteilt selbst. Keine Behauptung ohne Quelle.

Dieses Repository ist das **lauffähige MVP-Fundament** aus den drei Konzept-
Entwürfen (App-Konzept, Datenmodell, Redaktionelle Kriterien).

## Was drin ist

| Baustein | Umsetzung |
|----------|-----------|
| **Datenmodell** | Alle 11 Tabellen des Entwurfs als SQLAlchemy-Modelle (`app/models`), plus Vektor-Tabelle für RAG. Postgres + `pgvector`. |
| **Redaktionelle Kriterien als Code** | 3-Quellen-Regel, Kategorien (Kontroverse / Amtliche Feststellung / Meinung / Reaktion), Vertrauensstufen, Ausschlussliste – in `app/core/neutralitaet.py` und den Enums. |
| **REST-API** | FastAPI unter `/api` – Parteien, Politiker, Quellen, Ereignisse (mit automatischer Statusberechnung), Positionen, Abstimmungen, Methodik-Changelog, RAG-Fragen. Swagger unter `/docs`. |
| **Web-Ansicht** | Server-gerenderte Profil- & Timeline-Seiten (`/`, `/parteien/{id}`, `/ereignisse/{id}`, `/quellen/ausschlussliste`, `/fragen`). |
| **Nachrichten-Aggregation (3.2)** | `app/services/news.py` + `scripts/ingest_news.py` – RSS/Atom-Parser (stdlib), Duplikat-Erkennung (Titel-Hash), Near-Duplicate-**Clustering** für den Framing-Vergleich derselben Story über mehrere Quellen. Feed-Liste in `app/feeds.py`. |
| **NER-Tagging (Tech 6)** | `app/core/ner.py` – **spaCy-Hybrid** (deutsches Modell + Gazetteer) als scharfer Default, reiner Gazetteer als offline-Fallback. Meldungen werden automatisch verschlagwortet (`erwaehnungen`). |
| **Externe Quellen (5)** | `app/services/abgeordnetenwatch.py` (Politiker, Bürgerfragen) und `app/services/bundestag.py` (namentliche Abstimmungen, XML). Import-Skripte `scripts/import_politicians.py`, `scripts/import_votes.py`. Parser deterministisch gegen Fixtures getestet. |
| **Diff-Tracking + Prüfung** | `app/services/diff_tracking.py` + Cronjob `scripts/check_diffs.py` (Wayback-Vergleich, Hash-Diff). Manuelle **Vier-Augen-Prüfung** über `/api/snapshots/offen` und `/api/snapshots/{id}/pruefen` (Kriterien 4b/4c). |
| **RAG mit Zitations-Pflicht (3.3)** | `app/services/rag.py` – **echte semantische Embeddings** (spaCy-Wortvektoren, 300 Dim) über `pgvector`; optional Transformer (`sbert`) oder Hashing-Fallback. |
| **LLM-Layer (3.3/6)** | `app/core/llm.py` – belegpflichtige Antwortsynthese: **extraktiv** (deterministisch, keine Halluzination) als Default, optional **Anthropic-SDK** (`claude-opus-5`, strikter Zitations-Zwang) via `LLM=anthropic`. |
| **Audit-Log & Transparenz** | Jede Schreiboperation protokolliert (`audit_log`); Methodik-Änderungen im öffentlichen Changelog. |
| **Seed (Pilot AfD)** | `scripts/seed.py` – Partei, Politiker, Quellen, drei Beispiel-Ereignisse (u. a. Amtliche Feststellung, bestätigte und vorläufige Kontroverse). |

## Schnellstart

Voraussetzungen: Python 3.11+ und Docker (für Postgres mit pgvector).

```bash
# 1. Abhängigkeiten
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1b. spaCy-Modell MIT Wortvektoren (echtes NER + echte RAG-Embeddings, 300 Dim)
python -m spacy download de_core_news_md
#    Ohne dieses Modell läuft die App weiter, fällt aber automatisch auf
#    Gazetteer-NER + Hashing-Embeddings zurück (ohne echte Semantik).

# 2. Konfiguration
cp .env.example .env

# 3. Datenbank (Postgres + pgvector)
docker compose up -d

# 4. Schema anlegen
alembic upgrade head

# 5. Pilot-Daten laden (AfD)
python -m scripts.seed

# 6. App starten
uvicorn app.main:app --reload
```

Dann:
- Weboberfläche: <http://localhost:8000/>
- API-Doku (Swagger): <http://localhost:8000/docs>
- Health-Check: <http://localhost:8000/health>

### Wiederkehrende Jobs / Ingestion

```bash
python -m scripts.ingest_news          # RSS-Feeds abrufen & aggregieren (stündlich)
python -m scripts.check_diffs          # Diff-Tracking gegen Wayback (täglich)
python -m scripts.reindex              # RAG-Vektor-Index neu aufbauen
python -m scripts.import_politicians "AfD" --party-id 1   # abgeordnetenwatch
python -m scripts.import_votes abstimmung.xml             # Bundestag Open Data
```

> In dieser Ausführungsumgebung ist der ausgehende Netzwerkzugriff auf die
> externen Hosts gesperrt; die Abruf-Skripte laufen deshalb erst in einer
> Umgebung mit Netzzugang. Parsing, Dedup, Clustering, NER und Import sind
> davon unabhängig und vollständig getestet.

### Backends umschalten

Der scharfe Default nutzt **spaCy-Wortvektoren** (300 Dim, offline) für die
Embeddings und **spaCy-Hybrid-NER**. Alternativen per Umgebungsvariable:

```bash
# Transformer-Embeddings statt spaCy-Vektoren (benötigt Modell-Hub-Zugriff):
pip install sentence-transformers
export EMBEDDER=sbert EMBEDDING_DIM=384        # DB mit dieser Dimension neu aufbauen

# LLM-gestützte Antwortsynthese mit Zitations-Zwang (statt extraktiv):
pip install anthropic                          # Anmeldedaten via ANTHROPIC_API_KEY / ant auth
export LLM=anthropic

# Komplett ohne Modelle (zero-dependency Fallback):
export EMBEDDER=hashing EMBEDDING_DIM=384 NER=gazetteer
```

> Die Vektor-Spaltenbreite (`EMBEDDING_DIM`) muss zum aktiven Embedder passen;
> nach einem Wechsel die DB neu migrieren und `python -m scripts.reindex` laufen lassen.

## Tests

```bash
pytest
```

Die Kern-Regeln (3-Quellen-Logik, Embedding-Ähnlichkeit, Content-Hashing)
sind ohne laufende Datenbank testbar.

## Projektstruktur

```
app/
  models/        ORM (Datenmodell-Entwurf 1:1 + meldungen/erwaehnungen)
  enums.py       Kategorien/Status/Vertrauensstufen der Kriterien
  feeds.py       Konfigurierte Nachrichten-Feeds (über das Spektrum)
  schemas/       Pydantic-Ein-/Ausgaben
  core/          Neutralitäts-Regeln, Audit-Log, Embeddings, NER
  services/      news, diff_tracking, rag, abgeordnetenwatch, bundestag
  api/           REST-Router
  web/           Server-gerenderte Ansichten + neutrale Labels
  templates/     Jinja2-Templates
migrations/      Alembic (0001 Basis, 0002 news/ner)
scripts/         seed / ingest_news / check_diffs / reindex / import_*
tests/
```

## Scharfe Backends & Grenzen

Aktiv scharfgeschaltet (Default): **echte spaCy-Wortvektor-Embeddings** (300 Dim)
und **spaCy-Hybrid-NER**. Beide sind live gegen die DB verifiziert – semantische
Suche findet Paraphrasen ohne Wortüberlappung.

- **Transformer-Embeddings (`sbert`)** sind vollständig implementiert, aber in
  dieser Ausführungsumgebung nicht ladbar, weil der Egress-Proxy den Modell-Hub
  (HuggingFace) per Policy sperrt. In einer Umgebung mit Hub-Zugang genügt
  `EMBEDDER=sbert EMBEDDING_DIM=384`.
- **LLM-Antwortsynthese (`anthropic`)** ist mit dem offiziellen SDK implementiert
  (strikter Zitations-Zwang). Der Default bleibt der **extraktive** Summarizer
  (deterministisch, keine Halluzination); der Anthropic-Weg aktiviert sich mit
  `LLM=anthropic` und Anmeldedaten.
- **Externe Abrufe** (RSS, abgeordnetenwatch, Bundestag) rufen echte Endpunkte
  ab; die Hosts sind hier ebenfalls durch die Egress-Policy gesperrt. Parsing,
  Dedup, Clustering, NER und Import sind netz­unabhängig und getestet.
- **Seed-Ereignisse sind teils Demonstrationsdaten** und vor einem echten
  Betrieb redaktionell durch real belegte Ereignisse zu ersetzen.
