"""Tests des RSS/Atom-Parsers und der Titel-Normalisierung."""
from __future__ import annotations

from app.services.news import _titel_hash, parse_feed

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Beispiel</title>
  <item>
    <title>AfD stellt Antrag im Bundestag</title>
    <link>https://example.com/a</link>
    <description>Kurzbeschreibung A</description>
    <pubDate>Tue, 10 Sep 2024 12:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Zweite Meldung</title>
    <link>https://example.com/b</link>
  </item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Beispiel</title>
  <entry>
    <title>Atom-Artikel</title>
    <link href="https://example.com/atom1"/>
    <summary>Zusammenfassung</summary>
    <updated>2024-09-11T08:30:00Z</updated>
  </entry>
</feed>"""


def test_rss_parsing():
    items = parse_feed(RSS)
    assert len(items) == 2
    assert items[0].titel == "AfD stellt Antrag im Bundestag"
    assert items[0].url == "https://example.com/a"
    assert items[0].zusammenfassung == "Kurzbeschreibung A"
    assert items[0].veroeffentlicht_am is not None
    assert items[0].veroeffentlicht_am.year == 2024


def test_atom_parsing():
    items = parse_feed(ATOM)
    assert len(items) == 1
    assert items[0].titel == "Atom-Artikel"
    assert items[0].url == "https://example.com/atom1"
    assert items[0].veroeffentlicht_am.month == 9


def test_titel_hash_normalisiert():
    assert _titel_hash("AfD  stellt   Antrag") == _titel_hash("afd stellt antrag")
    assert _titel_hash("Titel A") != _titel_hash("Titel B")
