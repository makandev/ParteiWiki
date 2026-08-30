# ParteiWiki – App-Image (FastAPI + spaCy-Wortvektoren).
FROM python:3.11-slim

# Laufzeit-Abhängigkeiten für psycopg (libpq) und Healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Erst Requirements (Layer-Caching), dann das deutsche spaCy-Modell MIT Vektoren.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download de_core_news_md

COPY . .

ENV ENV=production \
    DATABASE_URL=postgresql+psycopg://parteiwiki:parteiwiki@db:5432/parteiwiki

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker/entrypoint.sh"]
