"""Tests des Gazetteer-NER (Wortgrenzen, längster Treffer, Aliase)."""
from __future__ import annotations

import uuid

from types import SimpleNamespace

from app.core.ner import GazetteerTagger, _Eintrag, _muster, nachnamen_eintraege


def _tagger():
    pol_id = uuid.uuid4()
    partei_id = uuid.uuid4()
    eintraege = [
        _Eintrag(_muster("AfD"), "AfD", None, partei_id, 3),
        _Eintrag(_muster("Alternative für Deutschland"), "AfD", None, partei_id, 27),
        _Eintrag(_muster("Alice Weidel"), "Alice Weidel", pol_id, partei_id, 12),
    ]
    return GazetteerTagger(eintraege), pol_id, partei_id


def test_erkennt_politiker_und_partei():
    tagger, pol_id, partei_id = _tagger()
    treffer = tagger.tag("Alice Weidel (AfD) sprach im Bundestag.")
    ziele = {(t.politiker_id, t.partei_id) for t in treffer}
    assert (pol_id, partei_id) in ziele
    assert (None, partei_id) in ziele


def test_alias_wird_erkannt():
    tagger, _, partei_id = _tagger()
    treffer = tagger.tag("Die Alternative für Deutschland stellte einen Antrag.")
    assert any(t.partei_id == partei_id for t in treffer)


def test_wortgrenze_keine_teiltreffer():
    tagger, _, _ = _tagger()
    # "AfDler" darf NICHT als Partei "AfD" matchen (Wortgrenze).
    treffer = tagger.tag("Ein AfDlerinnentreffen fand statt.")
    assert treffer == []


def test_keine_erkennung_ohne_treffer():
    tagger, _, _ = _tagger()
    assert tagger.tag("Das Wetter ist heute schön.") == []


# --- P1.3: konservative Nachnamen-Erkennung -------------------------------
def _pol(name, pid=None):
    return SimpleNamespace(name=name, id=pid or uuid.uuid4(), partei_id=uuid.uuid4())


def test_eindeutiger_nachname_wird_zugelassen():
    eintraege = nachnamen_eintraege([_pol("Alice Weidel")])
    assert len(eintraege) == 1
    assert eintraege[0].muster.search("Weidel fordert Neuwahlen")


def test_mehrdeutiger_nachname_wird_abgelehnt():
    # Zwei Politiker mit gleichem Nachnamen -> nicht eindeutig -> kein Muster.
    assert nachnamen_eintraege([_pol("Anna Müller"), _pol("Bernd Müller")]) == []


def test_haeufigwort_nachname_wird_abgelehnt():
    # "Wolf" steht auf der Stoppliste -> kein Nachnamen-Muster.
    assert nachnamen_eintraege([_pol("Frank Wolf")]) == []


def test_zu_kurzer_nachname_wird_abgelehnt():
    assert nachnamen_eintraege([_pol("Max Ott")]) == []


def test_nachname_kollidiert_mit_parteitoken():
    # "Linke" ist Token der Partei "Die Linke" -> kein Nachnamen-Muster,
    # damit eine Parteinennung nicht dem Politiker zugeschrieben wird.
    assert nachnamen_eintraege([_pol("Max Linke")], verbotene={"die", "linke"}) == []
    # Ohne Kollision wird derselbe Nachname zugelassen.
    assert len(nachnamen_eintraege([_pol("Max Linke")])) == 1
