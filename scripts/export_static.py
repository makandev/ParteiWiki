"""Exportiert eine statische Vorschau der echten UI nach ``docs/`` (GitHub Pages).

Rendert die server-generierten Ansichten aus den Seed-Daten und schreibt sie als
flache HTML-Dateien mit umgeschriebenen Links/Assets. Interaktive Funktionen
(Live-Suche/RAG, API) brauchen das Backend und funktionieren in der statischen
Vorschau nicht – darauf weist ein Banner hin.

Voraussetzung: erreichbare, geseedete DB (``DATABASE_URL``).
Aufruf:  python -m scripts.export_static
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Ereignis, Partei

REPO_URL = "https://github.com/makandev/ParteiWiki"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"

BANNER = (
    '<div style="background:#fef3c7;color:#92400e;border:1px solid #fde68a;'
    'border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:.9rem">'
    'Statische Vorschau (GitHub Pages): die echte Oberfläche zum Durchklicken, '
    'erzeugt aus den Seed-Daten. Live-Suche, Frage-Funktion und API laufen nur '
    f'im Betrieb mit Backend – siehe <a href="{REPO_URL}">Repository</a>.</div>'
)


def _rewrite(html: str) -> str:
    html = html.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    html = re.sub(r'href="/parteien/([0-9a-f-]+)"', r'href="partei-\1.html"', html)
    html = re.sub(r'href="/ereignisse/([0-9a-f-]+)"', r'href="ereignis-\1.html"', html)
    html = html.replace('href="/quellen/ausschlussliste"', 'href="ausschlussliste.html"')
    html = html.replace('href="/news"', 'href="news.html"')
    html = html.replace('href="/fragen"', 'href="fragen.html"')
    html = html.replace('href="/docs"', f'href="{REPO_URL}"')
    html = html.replace('href="/"', 'href="index.html"')
    # Formular auf der Fragen-Seite neutralisieren (kein Backend im statischen Modus).
    html = re.sub(r'<form method="post" action="/fragen"[^>]*>',
                  '<form class="frageform" onsubmit="return false">', html)
    html = html.replace('<main class="container">', '<main class="container">' + BANNER, 1)
    return html


def _speichere(client: TestClient, pfad: str, dateiname: str) -> None:
    resp = client.get(pfad)
    resp.raise_for_status()
    (OUT / dateiname).write_text(_rewrite(resp.text), encoding="utf-8")
    print(f"  {pfad}  ->  docs/{dateiname}")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(ROOT / "app" / "static", OUT / "static")
    # .nojekyll: verhindert Jekyll-Verarbeitung auf Pages (Ordner mit _ etc.).
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    client = TestClient(app)
    db = SessionLocal()
    try:
        parteien = db.scalars(select(Partei)).all()
        ereignisse = db.scalars(select(Ereignis)).all()
    finally:
        db.close()

    _speichere(client, "/", "index.html")
    _speichere(client, "/news", "news.html")
    _speichere(client, "/fragen", "fragen.html")
    _speichere(client, "/quellen/ausschlussliste", "ausschlussliste.html")
    for p in parteien:
        _speichere(client, f"/parteien/{p.id}", f"partei-{p.id}.html")
    for e in ereignisse:
        _speichere(client, f"/ereignisse/{e.id}", f"ereignis-{e.id}.html")

    print(f"\nFertig: {len(parteien)} Partei-, {len(ereignisse)} Ereignis-Seiten nach {OUT}")


if __name__ == "__main__":
    main()
