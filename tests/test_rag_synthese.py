"""Tests der belegpflichtigen Antwortsynthese (keine Behauptung ohne Quelle)."""
from __future__ import annotations

from types import SimpleNamespace

from app.enums import Ereigniskategorie, Ereignisstatus
from app.services.rag import Antwort, Beleg, Treffer, formuliere_antwort


def _ereignis(titel, kat=Ereigniskategorie.kontroverse, status=Ereignisstatus.bestaetigt):
    return SimpleNamespace(titel=titel, kategorie=kat, status=status)


def test_ohne_treffer_keine_behauptung():
    text = formuliere_antwort(Antwort(frage="Was ist mit X?", treffer=[]))
    assert "keine Aussage ohne Quelle" in text.lower() or "keine aussage ohne quelle" in text.lower()


def test_mit_treffer_enthaelt_quellen():
    t = Treffer(
        ereignis=_ereignis("Beispiel-Ereignis"),
        distanz=0.1,
        konfidenz_quellen=3,
        belege=[Beleg("FAZ", "Artikel", "https://faz.net/x")],
    )
    text = formuliere_antwort(Antwort(frage="Frage?", treffer=[t]))
    assert "Beispiel-Ereignis" in text
    assert "FAZ" in text
    assert "https://faz.net/x" in text  # Zitats-Pflicht: URL im Text


def test_amtliche_feststellung_wird_als_solche_ausgewiesen():
    t = Treffer(
        ereignis=_ereignis("Behörden-Bescheid", kat=Ereigniskategorie.amtliche_feststellung),
        distanz=0.2,
        konfidenz_quellen=1,
        belege=[Beleg("Amt", "Bescheid", "https://amt.example/1")],
    )
    text = formuliere_antwort(Antwort(frage="Frage?", treffer=[t]))
    assert "amtliche Feststellung" in text
