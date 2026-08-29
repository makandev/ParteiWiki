"""Tests der 3-Quellen-Regel (Redaktionelle Kriterien, Punkt 1 / 1a)."""
from __future__ import annotations

from types import SimpleNamespace

from app.core.neutralitaet import berechne_status, zaehle_unabhaengige_quellen
from app.enums import Ereigniskategorie, Ereignisstatus, Vertrauensstufe


def _quelle(qid, stufe=Vertrauensstufe.serioes):
    return SimpleNamespace(vertrauensstufe=stufe), qid


def _eq(qid, stufe=Vertrauensstufe.serioes):
    quelle = SimpleNamespace(vertrauensstufe=stufe)
    return SimpleNamespace(quelle=quelle, quelle_id=qid)


def _ereignis(kategorie, eqs):
    return SimpleNamespace(kategorie=kategorie, ereignis_quellen=eqs)


def test_eine_quelle_bleibt_vorlaeufig():
    e = _ereignis(Ereigniskategorie.kontroverse, [_eq("a")])
    assert zaehle_unabhaengige_quellen(None, e) == 1
    assert berechne_status(None, e) == Ereignisstatus.vorlaeufig


def test_drei_unabhaengige_quellen_bestaetigt():
    e = _ereignis(Ereigniskategorie.kontroverse, [_eq("a"), _eq("b"), _eq("c")])
    assert berechne_status(None, e) == Ereignisstatus.bestaetigt


def test_gleiche_quelle_zaehlt_einmal():
    # Dieselbe Agenturmeldung, dreifach weiterverbreitet -> nur eine Quelle.
    e = _ereignis(Ereigniskategorie.kontroverse, [_eq("a"), _eq("a"), _eq("a")])
    assert zaehle_unabhaengige_quellen(None, e) == 1
    assert berechne_status(None, e) == Ereignisstatus.vorlaeufig


def test_ausgeschlossene_quelle_zaehlt_nicht():
    e = _ereignis(
        Ereigniskategorie.kontroverse,
        [_eq("a"), _eq("b"), _eq("c", Vertrauensstufe.ausgeschlossen)],
    )
    assert zaehle_unabhaengige_quellen(None, e) == 2
    assert berechne_status(None, e) == Ereignisstatus.vorlaeufig


def test_amtliche_feststellung_immer_bestaetigt():
    # Kriterien 1a: nicht der 3-Quellen-Regel unterworfen.
    e = _ereignis(Ereigniskategorie.amtliche_feststellung, [_eq("a")])
    assert berechne_status(None, e) == Ereignisstatus.bestaetigt
