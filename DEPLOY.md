# Deployment

Zwei Wege – bewusst getrennt, weil sie unterschiedliche Dinge können:

| Ziel | Was läuft | Suche/RAG/DB? |
|------|-----------|---------------|
| **GitHub Pages** | statische Vorschau der Oberfläche (`docs/`) | ❌ nein (kein Backend) |
| **Container-Host** (Pi/VPS/Cloud) | die vollständige App | ✅ ja |

> **Wichtig:** GitHub Pages ist ein reiner Datei-Hoster und führt keinen Code
> aus. Die funktionsfähige App (FastAPI + Postgres + pgvector + spaCy) kann dort
> nicht laufen – Pages zeigt nur die statische, klickbare Vorschau. Für die echte
> Seite mit Live-Suche braucht es einen Host, der Container ausführt.

---

## 1. Funktionsfähig: Docker Compose (Pi5 / VPS)

Bringt Datenbank **und** App hoch; migriert und seedet beim Erststart automatisch.

```bash
docker compose up --build       # startet db (pgvector) + web (App)
# App:            http://localhost:8000
# API-Doku:       http://localhost:8000/docs
```

Details:
- `Dockerfile` installiert Abhängigkeiten **und** das spaCy-Modell `de_core_news_md`.
- `docker/entrypoint.sh` wartet auf die DB, legt die pgvector-Extension an, führt
  `alembic upgrade head` aus und seedet nur, wenn die DB leer ist (`SEED_ON_START=1`).
- Backends per Umgebungsvariablen in `docker-compose.yml` (Default: spaCy-Vektoren
  + spaCy-NER + extraktiver LLM-Layer). Für Transformer-Embeddings: `EMBEDDER=sbert`
  und `EMBEDDING_DIM=384` setzen (DB dann mit dieser Dimension neu aufbauen).

Hinter einen Reverse-Proxy (Caddy/nginx) für TLS/Domain stellen.

## 2. Funktionsfähig: kostenlose Cloud-Hosts (sofort öffentlich)

Damit bekommst du eine echte URL, ohne auf den Pi zu warten. Voraussetzung: der
Host bietet **Postgres mit pgvector**.

- **Render**: Web Service aus diesem Repo (Docker) + „Render Postgres" (pgvector
  per `CREATE EXTENSION vector` aktivierbar). `DATABASE_URL` als Env setzen.
- **Fly.io**: `fly launch` (nutzt das `Dockerfile`) + Fly Postgres; pgvector-Image
  oder Extension aktivieren.
- **Railway**: Deploy aus Repo + Postgres-Plugin (pgvector aktivieren).

In allen Fällen liest die App `DATABASE_URL` und die Backend-Variablen aus der
Umgebung; `entrypoint.sh` erledigt Migration + Erst-Seed.

## 3. Statische Vorschau: GitHub Pages

Zeigt die echte Oberfläche zum Durchklicken (aus den Seed-Daten), ohne Backend.

**Einrichten (einmalig):**
1. Diesen Branch nach `main` mergen (der Pages-Workflow triggert auf `main`).
2. Repo → **Settings → Pages → Source: „GitHub Actions"**.
3. Der Workflow `.github/workflows/pages.yml` veröffentlicht `docs/`.
   Die URL erscheint danach unter Settings → Pages (Form:
   `https://makandev.github.io/ParteiWiki/`).

**Vorschau neu erzeugen** (nach UI-/Daten-Änderungen), mit laufender, geseedeter DB:

```bash
python -m scripts.export_static     # schreibt docs/ neu
git add docs && git commit -m "docs: statische Vorschau aktualisiert"
```

In der Vorschau sind Live-Suche, Frage-Funktion und API bewusst inaktiv
(Banner weist darauf hin) – sie brauchen das Backend aus Weg 1 oder 2.
