"""Tests des abgeordnetenwatch-Parsers (API-v2-Form)."""
from __future__ import annotations

from app.services.abgeordnetenwatch import parse_politicians, parse_questions

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
