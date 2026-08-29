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
| **NER-Tagging (Tech 6)** | `app/core/ner.py` – Gazetteer-Tagger (offline, gegen bekannte Politiker/Partei-Namen), optionaler spaCy-Backend. Meldungen werden automatisch verschlagwortet (`erwaehnungen`). |
| **Externe Quellen (5)** | `app/services/abgeordnetenwatch.py` (Politiker, Bürgerfragen) und `app/services/bundestag.py` (namentliche Abstimmungen, XML). Import-Skripte `scripts/import_politicians.py`, `scripts/import_votes.py`. Parser deterministisch gegen Fixtures getestet. |
| **Diff-Tracking + Prüfung** | `app/services/diff_tracking.py` + Cronjob `scripts/check_diffs.py` (Wayback-Vergleich, Hash-Diff). Manuelle **Vier-Augen-Prüfung** über `/api/snapshots/offen` und `/api/snapshots/{id}/pruefen` (Kriterien 4b/4c). |
| **RAG mit Zitations-Pflicht (3.3)** | `app/services/rag.py` – Embeddings über `pgvector`, offline-fähiger Standard-Embedder (optional `sentence-transformers`), belegpflichtige Antwortsynthese (extraktiv, keine Behauptung ohne Quelle). |
| **Audit-Log & Transparenz** | Jede Schreiboperation protokolliert (`audit_log`); Methodik-Änderungen im öffentlichen Changelog. |
| **Seed (Pilot AfD)** | `scripts/seed.py` – Partei, Politiker, Quellen, drei Beispiel-Ereignisse (u. a. Amtliche Feststellung, bestätigte und vorläufige Kontroverse). |

## Schnellstart

Voraussetzungen: Python 3.11+ und Docker (für Postgres mit pgvector).

```bash
# 1. Abhängigkeiten
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

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

### Optionale, stärkere Backends

```bash
# Echtes multilinguales RAG-Embedding (384 Dim, passt zu EMBEDDING_DIM):
pip install sentence-transformers
export EMBEDDER=sbert

# Deutsches spaCy-NER statt reinem Gazetteer:
pip install spacy && python -m spacy download de_core_news_sm
```

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

## Bewusste Grenzen dieses Fundaments

- **Offline-Defaults statt schwerer Modelle**: Der Standard-Embedder und der
  Gazetteer-NER laufen ohne Modell-Download. Für den Produktivbetrieb sind
  `sentence-transformers` bzw. spaCy an klar markierten Stellen einschaltbar
  (siehe oben). Die Boilerplate-Erkennung im Diff-Hash ist bewusst einfach.
- **Externe Abrufe brauchen Netzzugang**: Die Ingestion-/Import-Skripte rufen
  echte Endpunkte ab; Parsing, Dedup, Clustering, NER und Import sind aber
  netz­unabhängig und getestet.
- **Seed-Ereignisse sind teils Demonstrationsdaten** und vor einem echten
  Betrieb redaktionell durch real belegte Ereignisse zu ersetzen.
- **LLM-Zusammenfassungen**: Die RAG-Antwort ist bewusst extraktiv und
  belegpflichtig (keine frei generierten Behauptungen). Ein optionaler
  LLM-Layer mit Zitations-Zwang lässt sich darüber ergänzen.
