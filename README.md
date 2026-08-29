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
| **Diff-Tracking (Gerüst)** | `app/services/diff_tracking.py` + Cronjob `scripts/check_diffs.py` (Wayback-Vergleich, Hash-Diff, „möglicherweise verändert" bis zur manuellen Prüfung). |
| **RAG (Gerüst)** | `app/services/rag.py` – Embeddings über `pgvector`, offline-fähiger Standard-Embedder, Zitations-Pflicht über `ereignis_id`. |
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

### Wiederkehrende Jobs

```bash
python -m scripts.check_diffs   # Diff-Tracking (als Cronjob, z. B. täglich)
python -m scripts.reindex       # RAG-Vektor-Index neu aufbauen
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
  models/        ORM (Datenmodell-Entwurf 1:1)
  enums.py       Kategorien/Status/Vertrauensstufen der Kriterien
  schemas/       Pydantic-Ein-/Ausgaben
  core/          Neutralitäts-Regeln, Audit-Log, Embeddings
  services/      Diff-Tracking, RAG
  api/           REST-Router
  web/           Server-gerenderte Ansichten
  templates/     Jinja2-Templates
migrations/      Alembic
scripts/         seed / check_diffs / reindex
tests/
```

## Bewusste Grenzen dieses Fundaments

- **Diff-Tracking und RAG sind Gerüste**: lauffähig und testbar, aber der
  Standard-Embedder ist ein Offline-Platzhalter (kein echtes Sprachmodell) und
  die Boilerplate-Erkennung im Diff-Hash ist bewusst einfach gehalten. Beides
  ist an klar markierten Stellen austauschbar.
- **Seed-Ereignisse sind teils Demonstrationsdaten** und vor einem echten
  Betrieb redaktionell durch real belegte Ereignisse zu ersetzen.
- **Ingestion** (RSS/Bundestag-API/abgeordnetenwatch) ist im Datenmodell und in
  den Endpunkten vorgesehen, aber noch nicht als automatischer Import gebaut.
