"""Tests des Content-Hashings im Diff-Tracking (Kriterien Punkt 4)."""
from __future__ import annotations

from app.services.diff_tracking import content_hash


def test_layout_aenderung_kein_diff():
    # Reine Whitespace-/Tag-Unterschiede sollen denselben Hash ergeben.
    a = "<p>Der  Text   des Artikels.</p>"
    b = "<div><p>Der Text des Artikels.</p></div>"
    assert content_hash(a) == content_hash(b)


def test_inhaltsaenderung_erzeugt_diff():
    a = "<p>Der Text des Artikels.</p>"
    b = "<p>Der Text des Artikels wurde geändert.</p>"
    assert content_hash(a) != content_hash(b)
