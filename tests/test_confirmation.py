"""Tests für CLI-Bestätigungsablauf geplanter Änderungen."""

from __future__ import annotations

from systemmanager_sagehelper.confirmation import bestaetige_aenderungen_cli


def test_bestaetige_aenderungen_cli_anwenden() -> None:
    """Die Eingabe ``anwenden`` muss als Zustimmung gewertet werden."""
    assert bestaetige_aenderungen_cli("diff", prompt=lambda _: "anwenden")


def test_bestaetige_aenderungen_cli_abbrechen() -> None:
    """Andere Eingaben müssen als Abbruch gewertet werden."""
    assert not bestaetige_aenderungen_cli("diff", prompt=lambda _: "abbrechen")
