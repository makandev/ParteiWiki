"""Tests der Kennzahlen-Stammdaten (DB-frei).

Prüft die redaktionelle Kern-Invariante: keine Zahl ohne Quelle, plausible
Werte, bekannte Parteien – gleiche Methodik für alle.
"""
from __future__ import annotations

from scripts.seed_kennzahlen import QUELLE_URL, WAHLEN
from scripts.seed_parteien import PARTEIEN

BEKANNTE_PARTEIEN = {name for name, *_ in PARTEIEN}


def test_jede_wahl_hat_quelle():
    assert QUELLE_URL.startswith("https://")


def test_werte_plausibel_und_partei_bekannt():
    for label, datum, ergebnisse in WAHLEN:
        assert label and datum is not None
        for name, prozent, vorlaeufig, bemerkung in ergebnisse:
            assert name in BEKANNTE_PARTEIEN, f"unbekannte Partei: {name}"
            assert 0 < prozent < 100, f"unplausibler Wert: {name} {prozent}"
            assert isinstance(vorlaeufig, bool)


def test_keine_partei_je_wahl_doppelt():
    for label, datum, ergebnisse in WAHLEN:
        namen = [n for n, *_ in ergebnisse]
        assert len(namen) == len(set(namen)), f"Partei doppelt in {label}"


def test_summe_pro_wahl_unter_hundert():
    # Zweitstimmen-Anteile aufsummiert bleiben < 100 % (nicht alle Parteien erfasst).
    for label, datum, ergebnisse in WAHLEN:
        summe = sum(p for _, p, _, _ in ergebnisse)
        assert summe < 100, f"{label}: Summe {summe} unplausibel"
