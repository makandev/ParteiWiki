"""Tests des LLM-Layers (offline-prüfbare Teile: Erdung, Fallback, Default)."""
from __future__ import annotations

from types import SimpleNamespace

from app.core.llm import ExtractiveSummarizer, _quellenblock, get_summarizer
from app.enums import Ereigniskategorie, Ereignisstatus
from app.services.rag import Antwort, Beleg, Treffer


def _treffer(titel, belege, kat=Ereigniskategorie.kontroverse):
    e = SimpleNamespace(
        titel=titel, kategorie=kat, status=Ereignisstatus.bestaetigt,
        beschreibung="Beschreibung",
    )
    return Treffer(ereignis=e, distanz=0.1, konfidenz_quellen=len(belege), belege=belege)


def test_quellenblock_nummeriert_ueber_treffer():
    a = Antwort(frage="F?", treffer=[
        _treffer("E1", [Beleg("dpa", "A1", "u1"), Beleg("FAZ", "A2", "u2")]),
        _treffer("E2", [Beleg("SZ", "A3", "u3")]),
    ])
    text, hat_quellen = _quellenblock(a)
    assert hat_quellen
    assert "[1]" in text and "[2]" in text and "[3]" in text
    assert "dpa" in text and "SZ" in text


def test_quellenblock_ohne_quellen():
    a = Antwort(frage="F?", treffer=[_treffer("E1", [])])
    _, hat_quellen = _quellenblock(a)
    assert hat_quellen is False


def test_default_summarizer_ist_extraktiv():
    assert isinstance(get_summarizer(), ExtractiveSummarizer)


def test_extraktiv_ohne_treffer_keine_behauptung():
    text = ExtractiveSummarizer().summarize(Antwort(frage="F?", treffer=[]))
    assert "keine aussage ohne quelle" in text.lower()
