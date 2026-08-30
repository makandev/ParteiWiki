#!/usr/bin/env bash
# Startsequenz des App-Containers: auf DB warten, migrieren, ggf. seeden, starten.
set -euo pipefail

echo "[entrypoint] warte auf die Datenbank ..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
for versuch in range(60):
    try:
        with create_engine(url).connect() as c:
            c.execute(text("SELECT 1"))
        print("[entrypoint] DB erreichbar.")
        break
    except Exception as exc:
        print(f"[entrypoint] DB noch nicht bereit ({exc}); neuer Versuch ...")
        time.sleep(2)
else:
    raise SystemExit("[entrypoint] DB nach 120s nicht erreichbar.")
PY

# pgvector-Extension sicherstellen (idempotent; benötigt ausreichende Rechte).
python - <<'PY'
import os
from sqlalchemy import create_engine, text
with create_engine(os.environ["DATABASE_URL"]).connect() as c:
    c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    c.commit()
    print("[entrypoint] pgvector bereit.")
PY

echo "[entrypoint] Migrationen ..."
alembic upgrade head

# Seed nur, wenn noch keine Partei existiert (idempotenter Erststart).
if [ "${SEED_ON_START:-1}" = "1" ]; then
  python - <<'PY'
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Partei
db = SessionLocal()
leer = db.scalar(select(Partei).limit(1)) is None
db.close()
if leer:
    print("[entrypoint] leere DB -> Seed (Pilot AfD).")
    from scripts.seed import seed
    seed()
else:
    print("[entrypoint] Daten vorhanden -> Seed übersprungen.")
PY
fi

echo "[entrypoint] starte uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
