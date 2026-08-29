"""LLM-Layer für Antwort-Zusammenfassung mit striktem Zitations-Zwang (Konzept 3.3/6).

Zwei Backends hinter einem gemeinsamen Interface:

* ``ExtractiveSummarizer`` (Default) – setzt die Antwort ausschließlich aus
  gespeicherten, neutralen Feldern und den konkreten Quellen zusammen. Erzeugt
  garantiert keine freien Behauptungen (keine Halluzination) und ist vollständig
  offline lauffähig und getestet.
* ``AnthropicSummarizer`` (optional) – nutzt das offizielle Anthropic-SDK
  (Modell ``claude-opus-5``), streng geerdet auf die übergebenen Quellen:
  Jede Aussage muss eine Quelle [n] zitieren, fehlt die Deckung, sagt das Modell
  das explizit. Wird nur aktiv, wenn ``LLM=anthropic`` gesetzt und Paket +
  Anmeldedaten vorhanden sind; sonst Fallback auf den extraktiven Summarizer.

Beide erfüllen die Konzept-Regel „Keine Behauptung ohne Quellenangabe".
"""
from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from app.config import settings
from app.web.labels import KATEGORIE_LABEL, STATUS_LABEL

if TYPE_CHECKING:  # nur für Typen, kein Laufzeit-Import-Zyklus
    from app.services.rag import Antwort


SYSTEM_PROMPT = (
    "Du bist ein neutrales Auskunftssystem. Beantworte die Frage AUSSCHLIESSLICH "
    "auf Basis der bereitgestellten Quellen. Regeln, ausnahmslos:\n"
    "1. Keine Aussage ohne Quellenangabe – belege jede Aussage mit [n].\n"
    "2. Bewerte nicht, ordne politisch nicht ein, ranke Parteien nicht.\n"
    "3. Trenne Fakten von Meinung; amtliche Feststellungen sind als solche zu "
    "benennen.\n"
    "4. Reichen die Quellen nicht, sage das ausdrücklich – erfinde nichts.\n"
    "Antworte knapp und sachlich auf Deutsch."
)


def _quellenblock(antwort: "Antwort") -> tuple[str, bool]:
    """Baut den nummerierten Quellenkontext. Rückgabe: (text, hat_quellen)."""
    zeilen: list[str] = []
    n = 0
    hat_quellen = False
    for t in antwort.treffer:
        e = t.ereignis
        kat = KATEGORIE_LABEL.get(e.kategorie.value, e.kategorie.value)
        stat = STATUS_LABEL.get(e.status.value, e.status.value)
        zeilen.append(f"Ereignis: {e.titel} (Kategorie: {kat}, Status: {stat})")
        if e.beschreibung:
            zeilen.append(f"  Beschreibung: {e.beschreibung}")
        for b in t.belege:
            n += 1
            hat_quellen = True
            titel = b.artikel_titel or b.artikel_url
            zeilen.append(f"  [{n}] {b.medienname}: {titel} ({b.artikel_url})")
    return "\n".join(zeilen), hat_quellen


class ExtractiveSummarizer:
    """Deterministische, belegpflichtige Antwort ohne freie Textgenerierung."""

    def summarize(self, antwort: "Antwort") -> str:
        if not antwort.treffer:
            return (
                "Zu dieser Frage ist kein belegtes Ereignis erfasst. Es wird "
                "bewusst keine Aussage ohne Quelle gemacht."
            )
        zeilen = [
            f"Zur Frage wurden {len(antwort.treffer)} erfasste Ereignisse gefunden. "
            "Alle Angaben stammen aus den verlinkten Quellen; die App bewertet nicht."
        ]
        for t in antwort.treffer:
            e = t.ereignis
            kat = KATEGORIE_LABEL.get(e.kategorie.value, e.kategorie.value)
            stat = STATUS_LABEL.get(e.status.value, e.status.value)
            if e.kategorie.value == "amtliche_feststellung":
                konf = "amtliche Feststellung (Originalquelle)"
            else:
                konf = f"{t.konfidenz_quellen} unabhängige Quelle(n)"
            zeilen.append(f"\n• {e.titel} — {kat}, Status: {stat}, Konfidenz: {konf}.")
            for b in t.belege:
                titel = b.artikel_titel or b.artikel_url
                zeilen.append(f"    – Quelle: {b.medienname}: {titel} <{b.artikel_url}>")
        return "\n".join(zeilen)


class AnthropicSummarizer:
    """LLM-gestützte Zusammenfassung, streng auf die Quellen geerdet."""

    def __init__(self, model: str):
        import anthropic  # lazy – nur wenn aktiviert

        self._client = anthropic.Anthropic()  # Anmeldedaten aus Umgebung/Profil
        self._model = model
        self._fallback = ExtractiveSummarizer()

    def summarize(self, antwort: "Antwort") -> str:
        kontext, hat_quellen = _quellenblock(antwort)
        if not hat_quellen:
            return self._fallback.summarize(antwort)
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1200,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Frage: {antwort.frage}\n\n"
                        f"Quellen (nur diese verwenden):\n{kontext}"
                    ),
                }],
            )
        except Exception as exc:  # pragma: no cover - Netz/Key-abhängig
            print(f"[llm] Anthropic-Aufruf fehlgeschlagen ({exc}) – extraktiver Fallback.")
            return self._fallback.summarize(antwort)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return text.strip() or self._fallback.summarize(antwort)


class Summarizer(Protocol):
    def summarize(self, antwort: "Antwort") -> str:
        ...


_summarizer: Summarizer | None = None


def get_summarizer() -> Summarizer:
    """Singleton-Zugriff auf den konfigurierten Summarizer (mit Fallback)."""
    global _summarizer
    if _summarizer is not None:
        return _summarizer
    if settings.llm.lower() == "anthropic":
        try:
            _summarizer = AnthropicSummarizer(settings.llm_model)
            return _summarizer
        except Exception as exc:  # pragma: no cover - Paket/Key-abhängig
            print(f"[llm] Anthropic nicht verfügbar ({exc}) – Fallback auf extraktiv.")
    _summarizer = ExtractiveSummarizer()
    return _summarizer
