"""Konfigurierte Nachrichten-Feeds – bewusst über das Spektrum verteilt.

Konzept 3.2 / Punkt 4 (Neutralität): seriöse Medienlandschaft, nicht nur ÖRR.
Die Liste ist der Startpunkt; Quellen werden im ``quellen``-Datensatz mit einer
Vertrauensstufe geführt und können dort ergänzt/ausgeschlossen werden.

Hinweis: Die konkreten Feed-URLs können sich ändern. Sie werden erst beim
Ingestion-Lauf abgerufen; die Verarbeitung (Parsing/Dedup/Clustering) ist
davon unabhängig testbar.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feed:
    medienname: str
    url: str
    url_basis: str


DEFAULT_FEEDS: list[Feed] = [
    Feed("tagesschau", "https://www.tagesschau.de/index~rss2.xml", "https://www.tagesschau.de"),
    Feed("Zeit", "https://newsfeed.zeit.de/index", "https://www.zeit.de"),
    Feed("FAZ", "https://www.faz.net/rss/aktuell/politik/", "https://www.faz.net"),
    Feed("SZ", "https://rss.sueddeutsche.de/rss/Politik", "https://www.sueddeutsche.de"),
    Feed("Welt", "https://www.welt.de/feeds/section/politik.rss", "https://www.welt.de"),
    Feed("taz", "https://taz.de/!p4608;rss/", "https://taz.de"),
    Feed("Spiegel", "https://www.spiegel.de/politik/deutschland/index.rss", "https://www.spiegel.de"),
]
