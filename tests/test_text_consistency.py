"""Tests für statische Textkonsistenz der sichtbaren Kerntexte."""

from __future__ import annotations

import subprocess


def test_textkonsistenz_check_ohne_treffer() -> None:
    """Der Konsistenzcheck soll ohne gemischte englische UI-Schlüsselbegriffe durchlaufen."""
    prozess = subprocess.run(
        ["python", "scripts/check_text_consistency.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prozess.returncode == 0, prozess.stdout + prozess.stderr
