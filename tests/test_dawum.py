"""Tests des DAWUM-Umfrage-Parsers (DB-frei)."""
from __future__ import annotations

from app.services.dawum import normalisiere_dawum_partei, parse_neueste_umfrage

DATENSATZ = {
    "Parliaments": {
        "0": {"Shortcut": "Bundestag", "Name": "Bundestag"},
        "1": {"Shortcut": "Bayern", "Name": "Bayern"},
    },
    "Institutes": {"1": {"Name": "INSA"}, "2": {"Name": "Forsa"}},
    "Parties": {
        "1": {"Shortcut": "CDU/CSU"},
        "2": {"Shortcut": "SPD"},
        "3": {"Shortcut": "Grüne"},
        "4": {"Shortcut": "AfD"},
        "5": {"Shortcut": "BSW"},
        "9": {"Shortcut": "Sonstige"},
    },
    "Surveys": {
        # ältere Bundestags-Umfrage
        "100": {"Date": "2025-08-01", "Parliament_ID": "0", "Institute_ID": "2",
                "Results": {"1": 27, "2": 15}},
        # jüngste Bundestags-Umfrage -> die soll gewählt werden
        "200": {"Date": "2025-08-25", "Parliament_ID": "0", "Institute_ID": "1",
                "Results": {"1": 28, "2": 16, "3": 12, "4": 21, "5": 4, "9": 8}},
        # anderes Parlament -> ignorieren
        "300": {"Date": "2025-09-01", "Parliament_ID": "1", "Institute_ID": "1",
                "Results": {"1": 40}},
    },
}


def test_normalisiere_dawum_partei():
    assert normalisiere_dawum_partei("CDU/CSU") == "CDU"
    assert normalisiere_dawum_partei("AfD") == "AfD"
    assert normalisiere_dawum_partei("BSW") == "BSW"
    assert normalisiere_dawum_partei("Sonstige") is None
    assert normalisiere_dawum_partei(None) is None


def test_parse_neueste_umfrage_waehlt_juengste_bundestagsumfrage():
    roh = parse_neueste_umfrage(DATENSATZ, parlament="Bundestag")
    assert roh is not None
    assert roh.datum == "2025-08-25"          # jüngste, nicht die 09-01 (Bayern)
    assert roh.institut == "INSA"
    assert roh.ergebnisse["AfD"] == 21.0
    assert roh.ergebnisse["CDU"] == 28.0      # Union der CDU zugeordnet
    assert roh.union_hinweis is True
    assert "Sonstige" not in roh.ergebnisse   # unbekannt -> verworfen


def test_parse_neueste_umfrage_kein_parlament():
    assert parse_neueste_umfrage({"Surveys": {}}, parlament="Bundestag") is None
