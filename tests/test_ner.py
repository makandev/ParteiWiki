"""Tests des Gazetteer-NER (Wortgrenzen, längster Treffer, Aliase)."""
from __future__ import annotations

import uuid

from app.core.ner import GazetteerTagger, _Eintrag, _muster


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
