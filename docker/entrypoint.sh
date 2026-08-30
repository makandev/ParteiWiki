#!/usr/bin/env bash
# Startsequenz des App-Containers: auf DB warten, migrieren, ggf. seeden, starten.
set -euo pipefail

echo "[entrypoint] warte auf die Datenbank ..."
python - <<'PY'
import time
from sqlalchemy import create_engine, text
from app.config import settings  # normalisiert postgres:// -> postgresql+psycopg://

url = settings.database_url
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

# Früher angelegte Demonstrationsdaten entfernen (idempotent; no-op wenn keine da).
python - <<'PY'
from app.database import SessionLocal
from scripts.cleanup_demo import bereinige_demo
db = SessionLocal()
try:
    ergebnis = bereinige_demo(db)
    if any(ergebnis.values()):
        print(f"[entrypoint] Demo-Daten entfernt: {ergebnis}")
finally:
    db.close()
PY

# Alle Parteien + kuratierte Quellen/Ausschlussliste + Wahlergebnis-Kennzahlen
# sicherstellen (idempotent).
python - <<'PY'
from app.database import SessionLocal
from scripts.seed_parteien import ensure_parteien
from scripts.seed import ensure_quellen
from scripts.seed_kennzahlen import ensure_kennzahlen
db = SessionLocal()
try:
    p = ensure_parteien(db)
    q = ensure_quellen(db)
    k = ensure_kennzahlen(db)
    if p or q or k:
        print(f"[entrypoint] ergaenzt: {p} Parteien, {q} Quellen, {k} Kennzahlen")
finally:
    db.close()
PY

echo "[entrypoint] starte uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
