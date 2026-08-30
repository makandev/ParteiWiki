"""Seed-Daten für den Pilot (Partei: AfD).

Die Neutralitätsregel gilt für die gesamte App: Diese Methodik und dieses
Skript sind 1:1 auf jede andere Partei übertragbar – nichts Partei-Spezifisches.
Die Ereignis-Beispiele unten sind teils als *Demonstrationsdaten* markiert und
vor einem echten Betrieb redaktionell (mit realen Quellen) zu ersetzen.

Aufruf:  python -m scripts.seed
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.core.neutralitaet import aktualisiere_status
from app.database import SessionLocal
from app.enums import Ereigniskategorie, Stimme, Vertrauensstufe
from app.models import (
    Abstimmung,
    Ereignis,
    EreignisQuelle,
    MethodikChangelog,
    Partei,
    Politiker,
    PositionsHistorie,
    Quelle,
)
from app.services.rag import index_ereignis


def _quelle(db, medienname, url_basis, stufe=Vertrauensstufe.serioes, begruendung=None):
    q = db.scalar(select(Quelle).where(Quelle.medienname == medienname))
    if q is None:
        q = Quelle(
            medienname=medienname,
            url_basis=url_basis,
            vertrauensstufe=stufe,
            ausschluss_begruendung=begruendung,
        )
        db.add(q)
        db.flush()
    return q


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(Partei).where(Partei.name == "AfD")):
            print("AfD bereits vorhanden – Seed übersprungen.")
            return

        partei = Partei(
            name="AfD",
            kurzbeschreibung=(
                "Deutsche politische Partei, gegründet 2013; seit 2017 im "
                "Deutschen Bundestag vertreten. (Neutrale Kurzbeschreibung.)"
            ),
            gruendungsjahr=2013,
            programm_url="https://www.afd.de/grundsatzprogramm/",
            letzte_aktualisierung=dt.date.today(),
        )
        db.add(partei)
        db.flush()

        weidel = Politiker(
            partei_id=partei.id, name="Alice Weidel", amt="Bundessprecherin (Co-Vorsitz), MdB"
        )
        chrupalla = Politiker(
            partei_id=partei.id, name="Tino Chrupalla", amt="Bundessprecher (Co-Vorsitz), MdB"
        )
        db.add_all([weidel, chrupalla])
        db.flush()

        # Quellen (inkl. je einem Beispiel "mit Vorsicht" und "ausgeschlossen").
        dpa = _quelle(db, "dpa", "https://www.dpa.com")
        faz = _quelle(db, "FAZ", "https://www.faz.net")
        reuters = _quelle(db, "Reuters", "https://www.reuters.com")
        sz = _quelle(db, "SZ", "https://www.sueddeutsche.de")
        _quelle(db, "Beispiel-Boulevardblog", "https://beispiel-blog.example",
                Vertrauensstufe.mit_vorsicht, "Nur mit Vorsicht: gemischte Redaktionsqualität.")
        _quelle(db, "Beispiel-Satireportal", "https://satire.example",
                Vertrauensstufe.ausgeschlossen, "Satire, keine Faktenberichterstattung (Kriterien 4d).")

        # Positions-Historie (Demonstrationsbeispiel).
        db.add(PositionsHistorie(
            partei_id=partei.id,
            thema="Beispiel: Position zu Thema X (Demonstrationsdaten)",
            position_alt="frühere Formulierung laut Programmversion A",
            position_neu="aktuelle Formulierung laut Programmversion B",
            geaendert_am=dt.date(2021, 6, 1),
            quelle_url="https://www.afd.de/grundsatzprogramm/",
        ))

        # Abstimmungen (Demonstrationsbeispiele; real aus Bundestag Open Data).
        db.add_all([
            Abstimmung(politiker_id=weidel.id, thema="Beispiel-Namentliche Abstimmung 1",
                       datum=dt.date(2023, 3, 17), stimme=Stimme.dagegen,
                       quelle_url="https://www.bundestag.de/services/opendata"),
            Abstimmung(politiker_id=chrupalla.id, thema="Beispiel-Namentliche Abstimmung 1",
                       datum=dt.date(2023, 3, 17), stimme=Stimme.dagegen,
                       quelle_url="https://www.bundestag.de/services/opendata"),
        ])

        # --- Ereignis 1: Amtliche Feststellung (nicht der 3-Quellen-Regel unterworfen) ---
        e_amt = Ereignis(
            partei_id=partei.id,
            titel="Einstufung durch das Bundesamt für Verfassungsschutz",
            beschreibung=(
                "Amtliche/behördliche Einstufung. Neutral als Fakt dargestellt, "
                "mit Verweis auf die Originalquelle; keine Bewertung durch die App. "
                "(Seed-Beispiel – redaktionell zu prüfen und zu aktualisieren.)"
            ),
            kategorie=Ereigniskategorie.amtliche_feststellung,
            datum_ereignis=dt.date(2021, 3, 3),
            gegendarstellung_url="https://www.afd.de/",
        )
        db.add(e_amt)
        db.flush()
        db.add(EreignisQuelle(
            ereignis_id=e_amt.id, quelle_id=faz.id,
            artikel_url="https://www.verfassungsschutz.de/",
            artikel_titel="Originalquelle: behördlicher Bescheid / Mitteilung",
        ))

        # --- Ereignis 2: Kontroverse, bestätigt (3 unabhängige Quellen) ---
        e_best = Ereignis(
            partei_id=partei.id,
            titel="Beispiel-Kontroverse A (Demonstrationsdaten)",
            beschreibung=(
                "Illustriert die 3-Quellen-Regel: bestätigt, weil drei voneinander "
                "unabhängige, seriöse Medien berichten."
            ),
            kategorie=Ereigniskategorie.kontroverse,
            datum_ereignis=dt.date(2024, 9, 10),
        )
        db.add(e_best)
        db.flush()
        for q, titel in [(dpa, "Meldung dpa"), (reuters, "Bericht Reuters"), (sz, "Einordnung SZ")]:
            db.add(EreignisQuelle(
                ereignis_id=e_best.id, quelle_id=q.id,
                artikel_url=f"https://example.com/{q.medienname.lower()}/kontroverse-a",
                artikel_titel=titel,
            ))

        # --- Ereignis 3: Kontroverse, vorläufig (nur 1 Quelle, Breaking News) ---
        e_vorl = Ereignis(
            partei_id=partei.id,
            titel="Beispiel-Kontroverse B (Demonstrationsdaten, Breaking News)",
            beschreibung=(
                "Illustriert den Zwischenstatus: erst eine Quelle vorhanden, daher "
                "'vorläufig – wird geprüft'. Wechselt automatisch auf 'bestätigt', "
                "sobald drei unabhängige Quellen erfasst sind."
            ),
            kategorie=Ereigniskategorie.kontroverse,
            datum_ereignis=dt.date(2025, 1, 15),
        )
        db.add(e_vorl)
        db.flush()
        db.add(EreignisQuelle(
            ereignis_id=e_vorl.id, quelle_id=dpa.id,
            artikel_url="https://example.com/dpa/kontroverse-b",
            artikel_titel="Erste Meldung dpa",
        ))

        # Status ableiten + RAG-Index bauen.
        db.flush()
        for e in (e_amt, e_best, e_vorl):
            db.refresh(e)
            aktualisiere_status(db, e)
            index_ereignis(db, e)

        # Transparenz: Seed im Methodik-Changelog dokumentieren.
        db.add(MethodikChangelog(
            was_geaendert="Initiale Kriterien, Datenmodell und Seed-Daten (Pilot AfD) angelegt.",
            warum=(
                "Pilotstart. Ereignis-Beispiele sind als Demonstrationsdaten "
                "markiert und vor Produktivbetrieb durch real belegte Ereignisse "
                "zu ersetzen. Gleiche Methodik gilt für jede Partei."
            ),
        ))

        db.commit()
        print("Seed abgeschlossen: Partei AfD, 2 Politiker, 6 Quellen, 3 Ereignisse.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
