"""Tests des abgeordnetenwatch-Parsers (API-v2-Form)."""
from __future__ import annotations

from app.services.abgeordnetenwatch import (
    normalisiere_partei,
    parse_mandate,
    parse_politicians,
    parse_questions,
)

POLITICIANS = {
    "meta": {"result": {"count": 2, "total": 2, "range_start": 0, "range_end": 100}},
    "data": [
        {"id": 1, "entity_type": "politician", "label": "Alice Weidel",
         "first_name": "Alice", "last_name": "Weidel",
         "party": {"id": 1, "entity_type": "party", "label": "AfD"}},
        {"id": 2, "entity_type": "politician", "label": "Tino Chrupalla",
         "first_name": "Tino", "last_name": "Chrupalla",
         "party": {"id": 1, "label": "AfD"}},
    ],
}

QUESTIONS = {
    "data": [
        {"id": 10, "entity_type": "question",
         "questions_text": "Wie stehen Sie zur Rentenpolitik?",
         "politician": {"id": 1, "label": "Alice Weidel"},
         "answers": [{"id": 5, "answer_text": "Wir fordern eine Reform.", "date": "2024-05-01"}]},
    ],
}


def test_parse_politicians():
    pol = parse_politicians(POLITICIANS)
    assert len(pol) == 2
    assert pol[0].name == "Alice Weidel"
    assert pol[0].partei_label == "AfD"
    assert pol[1].nachname == "Chrupalla"


def test_parse_questions():
    fragen = parse_questions(QUESTIONS)
    assert len(fragen) == 1
    assert fragen[0].politiker_label == "Alice Weidel"
    assert fragen[0].antworten[0].text == "Wir fordern eine Reform."


def test_leere_antwort():
    payload = {"data": [{"id": 1, "questions_text": "Frage?", "politician": {}, "answers": []}]}
    fragen = parse_questions(payload)
    assert fragen[0].antworten == []


# --- Mandate / MdB ---------------------------------------------------------
MANDATE = {
    "meta": {"result": {"count": 4}},
    "data": [
        {"id": 100, "type": "mandate", "label": "Alice Weidel (Bundestag 2025)",
         "politician": {"id": 1, "label": "Alice Weidel"},
         "party": {"id": 1, "label": "AfD"}},
        {"id": 101, "type": "mandate",
         "politician": {"id": 2, "label": "Friedrich Merz"},
         "party": {"id": 2, "label": "CDU"}},
        # Partei nur über Fraktionszugehörigkeit ableitbar.
        {"id": 102, "type": "mandate",
         "politician": {"id": 3, "label": "Britta Haßelmann"},
         "party": None,
         "fraction_membership": [{"fraction": {"label": "BÜNDNIS 90/DIE GRÜNEN"}}]},
        # Kandidatur (kein Mandat) wird ignoriert.
        {"id": 103, "type": "candidacy",
         "politician": {"id": 4, "label": "Niemand"},
         "party": {"id": 9, "label": "XYZ"}},
    ],
}


def test_parse_mandate_extrahiert_nur_mandate():
    mandate = parse_mandate(MANDATE)
    namen = {m.politiker_name for m in mandate}
    assert namen == {"Alice Weidel", "Friedrich Merz", "Britta Haßelmann"}
    # Kandidatur (type != mandate) ist nicht enthalten.
    assert "Niemand" not in namen


def test_parse_mandate_partei_aus_fraktion():
    mandate = {m.politiker_name: m for m in parse_mandate(MANDATE)}
    assert mandate["Britta Haßelmann"].partei_label == "BÜNDNIS 90/DIE GRÜNEN"


def test_normalisiere_partei():
    assert normalisiere_partei("AfD") == "AfD"
    assert normalisiere_partei("BÜNDNIS 90/DIE GRÜNEN") == "Grüne"
    assert normalisiere_partei("DIE LINKE.") == "Die Linke"
    assert normalisiere_partei("Freie Wähler") == "Freie Wähler"
    # Unbekanntes Label bleibt unzugeordnet (kein Rateverfahren).
    assert normalisiere_partei("Irgendeine Kleinpartei") is None
    assert normalisiere_partei(None) is None
