"""Tests des Bundestag-Abstimmungs-Parsers (namentliche Abstimmung)."""
from __future__ import annotations

from app.enums import Stimme
from app.services.bundestag import parse_namentliche_abstimmung

XML = """<?xml version="1.0" encoding="UTF-8"?>
<AbstimmungExport>
  <WAHLPERIODE>20</WAHLPERIODE>
  <ABSTIMMUNGSTITEL>Gesetz zur Beispielreform</ABSTIMMUNGSTITEL>
  <ABSTIMMUNGSDATUM>2024-03-17</ABSTIMMUNGSDATUM>
  <ABGEORDNETER>
    <VORNAME>Alice</VORNAME><NAME>Weidel</NAME><FRAKTION>AfD</FRAKTION>
    <JA>0</JA><NEIN>1</NEIN><ENTHALTUNG>0</ENTHALTUNG><NICHTABGEGEBEN>0</NICHTABGEGEBEN>
  </ABGEORDNETER>
  <ABGEORDNETER>
    <VORNAME>Max</VORNAME><NAME>Mustermann</NAME><FRAKTION>SPD</FRAKTION>
    <JA>1</JA><NEIN>0</NEIN><ENTHALTUNG>0</ENTHALTUNG><NICHTABGEGEBEN>0</NICHTABGEGEBEN>
  </ABGEORDNETER>
  <ABGEORDNETER>
    <VORNAME>Erika</VORNAME><NAME>Beispiel</NAME><FRAKTION>CDU</FRAKTION>
    <JA>0</JA><NEIN>0</NEIN><ENTHALTUNG>1</ENTHALTUNG><NICHTABGEGEBEN>0</NICHTABGEGEBEN>
  </ABGEORDNETER>
  <ABGEORDNETER>
    <VORNAME>Klaus</VORNAME><NAME>Fehlt</NAME><FRAKTION>FDP</FRAKTION>
    <JA>0</JA><NEIN>0</NEIN><ENTHALTUNG>0</ENTHALTUNG><NICHTABGEGEBEN>1</NICHTABGEGEBEN>
  </ABGEORDNETER>
</AbstimmungExport>"""


def test_meta_und_anzahl():
    meta = parse_namentliche_abstimmung(XML)
    assert meta.thema == "Gesetz zur Beispielreform"
    assert meta.wahlperiode == "20"
    assert meta.datum.isoformat() == "2024-03-17"
    assert len(meta.saetze) == 4


def test_stimm_mapping():
    meta = parse_namentliche_abstimmung(XML)
    by_name = {(s.vorname, s.nachname): s.stimme for s in meta.saetze}
    assert by_name[("Alice", "Weidel")] == Stimme.dagegen
    assert by_name[("Max", "Mustermann")] == Stimme.dafuer
    assert by_name[("Erika", "Beispiel")] == Stimme.enthalten
    assert by_name[("Klaus", "Fehlt")] == Stimme.nicht_anwesend
