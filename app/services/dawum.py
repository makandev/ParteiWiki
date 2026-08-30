"""Client für die offene Umfrage-Datenbank DAWUM (api.dawum.de, CC0).

Liefert Sonntagsfragen zur Bundestagswahl. Parsing ist vom Netzabruf getrennt
und deterministisch gegen Fixtures testbar; der Live-Abruf ist in dieser
Bau-Umgebung durch die Egress-Policy gesperrt und läuft auf dem Server.

API-Form (Auszug):
    GET https://api.dawum.de/
    -> {
         "Parliaments": {"0": {"Shortcut": "Bundestag", ...}, ...},
         "Institutes":  {"1": {"Name": "INSA", ...}, ...},
         "Parties":     {"1": {"Shortcut": "CDU/CSU"}, "2": {"Shortcut": "SPD"}, ...},
         "Surveys":     {"3400": {"Date": "2025-08-25", "Parliament_ID": "0",
                                   "Institute_ID": "1", "Results": {"1": 28, ...}}, ...}
       }
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

BASE = "https://api.dawum.de/"

# DAWUM-Kürzel -> unsere Parteinamen (scripts/seed_parteien.py). Umfragen führen
# die Union als "CDU/CSU" zusammen; dieser Wert wird der CDU zugeordnet und als
# Unionswert gekennzeichnet (die CSU wird separat nicht umfragebasiert geführt).
DAWUM_NORMALISIERUNG: dict[str, str] = {
    "cdu/csu": "CDU",
    "cdu": "CDU",
    "csu": "CSU",
    "spd": "SPD",
    "grüne": "Grüne",
    "grüne/b90": "Grüne",
    "fdp": "FDP",
    "afd": "AfD",
    "linke": "Die Linke",
    "die linke": "Die Linke",
    "bsw": "BSW",
    "freie wähler": "Freie Wähler",
    "fw": "Freie Wähler",
}


@dataclass
class UmfrageRoh:
    """Eine Sonntagsfrage (ein Institut, ein Datum) je Partei aufgeschlüsselt."""
    datum: str | None
    institut: str | None
    # {parteiname: prozent} – bereits auf unsere Parteinamen normalisiert.
    ergebnisse: dict[str, float] = field(default_factory=dict)
    union_hinweis: bool = False


def normalisiere_dawum_partei(shortcut: str | None) -> str | None:
    if not shortcut:
        return None
    return DAWUM_NORMALISIERUNG.get(shortcut.strip().casefold())


def parse_neueste_umfrage(payload: dict, *, parlament: str = "Bundestag") -> UmfrageRoh | None:
    """Wählt die jüngste Umfrage des genannten Parlaments und schlüsselt sie auf."""
    parlamente = payload.get("Parliaments") or {}
    institute = payload.get("Institutes") or {}
    parteien = payload.get("Parties") or {}
    surveys = payload.get("Surveys") or {}

    ziel_ids = {
        pid for pid, p in parlamente.items()
        if isinstance(p, dict) and (p.get("Shortcut") or p.get("Name")) == parlament
    }
    if not ziel_ids:
        return None

    kandidaten = [
        s for s in surveys.values()
        if isinstance(s, dict) and s.get("Parliament_ID") in ziel_ids and s.get("Date")
    ]
    if not kandidaten:
        return None
    neueste = max(kandidaten, key=lambda s: s.get("Date", ""))

    institut = None
    inst = institute.get(neueste.get("Institute_ID"))
    if isinstance(inst, dict):
        institut = inst.get("Name")

    ergebnisse: dict[str, float] = {}
    union = False
    for partei_id, prozent in (neueste.get("Results") or {}).items():
        pinfo = parteien.get(partei_id) or {}
        shortcut = pinfo.get("Shortcut") if isinstance(pinfo, dict) else None
        name = normalisiere_dawum_partei(shortcut)
        if name is None:
            continue
        try:
            wert = float(prozent)
        except (TypeError, ValueError):
            continue
        # Bei Doppelzuordnung (sollte selten sein) den ersten Wert behalten.
        ergebnisse.setdefault(name, wert)
        if (shortcut or "").casefold() == "cdu/csu":
            union = True
    return UmfrageRoh(
        datum=neueste.get("Date"), institut=institut,
        ergebnisse=ergebnisse, union_hinweis=union,
    )


class DawumClient:
    """Dünner HTTP-Client; ein GET liefert den gesamten Datensatz."""

    def __init__(self, base: str = BASE, client: httpx.Client | None = None):
        self.base = base
        self._client = client or httpx.Client(
            headers={"User-Agent": "ParteiWiki/0.1"}, timeout=30
        )

    def neueste_umfrage(self, *, parlament: str = "Bundestag") -> UmfrageRoh | None:
        resp = self._client.get(self.base)
        resp.raise_for_status()
        return parse_neueste_umfrage(resp.json(), parlament=parlament)

    def close(self) -> None:
        self._client.close()
