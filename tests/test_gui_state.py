"""Tests für die GUI-Persistenzschicht."""

from __future__ import annotations

from pathlib import Path

from systemmanager_sagehelper.gui_state import GUIStateStore


def test_lade_default_ohne_datei(tmp_path: Path) -> None:
    """Ohne Datei soll ein valider Standardzustand geliefert werden."""
    store = GUIStateStore(tmp_path / "gui_state.json")

    zustand = store.lade_gesamtzustand()

    assert "modules" in zustand
    assert "server_analysis" in zustand["modules"]


def test_speichere_und_lade_modulzustand(tmp_path: Path) -> None:
    """Modulzustände sollen verlustfrei gespeichert und geladen werden."""
    store = GUIStateStore(tmp_path / "gui_state.json")
    modulzustand = {
        "serverlisten": [{"servername": "srv-01"}],
        "rollen": {"srv-01": ["APP"]},
        "letzte_discovery_range": "192.168.1.1-10",
        "ausgabepfade": {"analyse_report": "docs/a.md", "log_report": "logs/b.md"},
        "letzte_kerninfos": ["Analysierte Server: 1"],
        "bericht_verweise": ["docs/a.md"],
    }

    store.speichere_modulzustand("server_analysis", modulzustand)
    geladen = store.lade_modulzustand("server_analysis")

    assert geladen["serverlisten"][0]["servername"] == "srv-01"
    assert geladen["rollen"]["srv-01"] == ["APP"]
    assert geladen["ausgabepfade"]["analyse_report"] == "docs/a.md"
