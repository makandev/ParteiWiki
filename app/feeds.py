"""Kuratierte Nachrichten-Feeds – bewusst über das politische Spektrum verteilt.

Grundsatz (Konzept 3.2 / Punkt 4): seriöse Medienlandschaft, links wie rechts,
inklusive oppositioneller/kritischer Stimmen – aber **kein Satire, kein Fake,
keine Propaganda**. Jede Quelle trägt eine Vertrauensstufe:

* ``serioes``       – etablierte journalistische Medien mit redaktioneller
                      Kontrolle (Pressekodex), quer über das Spektrum.
* ``mit_vorsicht``  – seriös betrieben, aber stark meinungs-/haltungsbetont
                      (klar erkennbare Ausrichtung) – wird mitgeführt, aber
                      gekennzeichnet.
* ``ausgeschlossen``– Satire ODER Falschmeldungs-/Propaganda-Quellen; werden
                      NICHT aggregiert und öffentlich mit Begründung geführt.

Die konkreten Feed-URLs können sich ändern; fehlschlagende Feeds werden beim
Ingestion-Lauf einzeln übersprungen und geloggt. Vertrauensstufen/Auswahl sind
bewusst anpassbar (redaktionelle Entscheidung, gilt für alle Parteien gleich).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.enums import Vertrauensstufe


@dataclass(frozen=True)
class Feed:
    medienname: str
    url: str
    url_basis: str
    vertrauensstufe: Vertrauensstufe = Vertrauensstufe.serioes
    spektrum: str = "mitte"  # links | mitte-links | mitte | mitte-rechts | rechts | agentur


# Etablierte, seriöse Medien quer über das Spektrum (werden aggregiert).
DEFAULT_FEEDS: list[Feed] = [
    # Öffentlich-rechtlich / Mitte
    Feed("tagesschau", "https://www.tagesschau.de/index~rss2.xml", "https://www.tagesschau.de", spektrum="mitte"),
    Feed("ZDFheute", "https://www.zdf.de/rss/zdf/nachrichten", "https://www.zdf.de", spektrum="mitte"),
    Feed("Deutschlandfunk", "https://www.deutschlandfunk.de/nachrichten-100.rss", "https://www.deutschlandfunk.de", spektrum="mitte"),
    Feed("Tagesspiegel", "https://www.tagesspiegel.de/contentexport/feed/home", "https://www.tagesspiegel.de", spektrum="mitte"),
    # Linksliberal / links
    Feed("Zeit", "https://newsfeed.zeit.de/index", "https://www.zeit.de", spektrum="mitte-links"),
    Feed("SZ", "https://rss.sueddeutsche.de/rss/Politik", "https://www.sueddeutsche.de", spektrum="mitte-links"),
    Feed("Spiegel", "https://www.spiegel.de/politik/deutschland/index.rss", "https://www.spiegel.de", spektrum="mitte-links"),
    Feed("Frankfurter Rundschau", "https://www.fr.de/politik/rssfeed.rdf", "https://www.fr.de", spektrum="links"),
    Feed("taz", "https://taz.de/!p4608;rss/", "https://taz.de", spektrum="links"),
    # Konservativ / wirtschaftsliberal / rechts der Mitte
    Feed("FAZ", "https://www.faz.net/rss/aktuell/politik/", "https://www.faz.net", spektrum="mitte-rechts"),
    Feed("Welt", "https://www.welt.de/feeds/section/politik.rss", "https://www.welt.de", spektrum="mitte-rechts"),
    Feed("Handelsblatt", "https://www.handelsblatt.com/contentexport/feed/politik", "https://www.handelsblatt.com", spektrum="mitte-rechts"),
    Feed("NZZ", "https://www.nzz.ch/international.rss", "https://www.nzz.ch", spektrum="mitte-rechts"),
    # Agentur
    Feed("Reuters", "https://feeds.reuters.com/reuters/GERtopNews", "https://www.reuters.com", spektrum="agentur"),
    # Meinungsstark, seriös betrieben – gekennzeichnet mitführen (Opposition beider Seiten)
    Feed("Cicero", "https://www.cicero.de/rss.xml", "https://www.cicero.de",
         vertrauensstufe=Vertrauensstufe.mit_vorsicht, spektrum="mitte-rechts"),
    Feed("nd", "https://www.nd-aktuell.de/rss/politik.xml", "https://www.nd-aktuell.de",
         vertrauensstufe=Vertrauensstufe.mit_vorsicht, spektrum="links"),
]

# Öffentlich geführte Ausschlussliste (Satire ODER Falschmeldung/Propaganda).
# (medienname, url_basis, begruendung)
AUSGESCHLOSSENE: list[tuple[str, str, str]] = [
    ("Der Postillon", "https://www.der-postillon.com", "Satire – keine Faktenberichterstattung."),
    ("Titanic", "https://www.titanic-magazin.de", "Satire – keine Faktenberichterstattung."),
    ("RT DE", "https://rtde.site", "Russisches Staatsmedium; in der EU wegen Desinformation sanktioniert."),
    ("Sputnik", "https://snanews.de", "Russisches Staatsmedium (Propaganda)."),
    ("COMPACT", "https://www.compact-online.de", "Vom Bundesinnenministerium als gesichert extremistisch eingestuft."),
    ("PI-News", "https://www.pi-news.net", "Nicht-journalistischer Blog ohne redaktionelle Kontrolle; wiederholt Falschmeldungen."),
    ("Journalistenwatch", "https://www.journalistenwatch.com", "Nicht-journalistischer Blog ohne redaktionelle Kontrolle."),
]
