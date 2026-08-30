"""Neutrale, menschenlesbare Beschriftungen für Enum-Werte.

Bewusst wertfrei formuliert – die App bewertet nicht, sie beschreibt nur.
"""
from __future__ import annotations

KATEGORIE_LABEL = {
    "kontroverse": "Kontroverse",
    "amtliche_feststellung": "Amtliche Feststellung",
    "meinung": "Meinung",
    "reaktion_zitat": "Reaktion / Zitat",
}

STATUS_LABEL = {
    "vorlaeufig": "vorläufig – wird geprüft",
    "bestaetigt": "bestätigt",
}

SNAPSHOT_LABEL = {
    "original": "Original",
    "moeglicherweise_veraendert": "möglicherweise verändert – wird geprüft",
    "bestaetigt_veraendert": "bestätigt verändert",
    "entfernt": "entfernt",
}

# Politische Orientierung je Medium (neutraler Hinweis, keine Wertung der Inhalte).
SPEKTRUM_LABEL = {
    "links": "links",
    "mitte-links": "Mitte-links",
    "mitte": "Mitte / neutral",
    "mitte-rechts": "Mitte-rechts",
    "rechts": "rechts",
    "agentur": "Nachrichtenagentur",
}

VERTRAUEN_LABEL = {
    "serioes": "seriös",
    "mit_vorsicht": "mit Vorsicht",
    "ausgeschlossen": "ausgeschlossen",
}
