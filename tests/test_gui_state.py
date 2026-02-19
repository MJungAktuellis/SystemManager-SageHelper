"""Tests für die GUI-Persistenzschicht."""

from __future__ import annotations

from pathlib import Path

from systemmanager_sagehelper.gui_state import GUIStateStore, erstelle_installer_modulzustand


def test_lade_default_ohne_datei(tmp_path: Path) -> None:
    """Ohne Datei soll ein valider Standardzustand geliefert werden."""
    store = GUIStateStore(tmp_path / "gui_state.json")

    zustand = store.lade_gesamtzustand()

    assert "modules" in zustand
    assert "server_analysis" in zustand["modules"]
    assert zustand["onboarding"]["onboarding_abgeschlossen"] is False


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
        "letzter_exportpfad": "docs/a.md",
        "letzter_exportzeitpunkt": "2026-01-02T03:04:05",
        "letzte_export_lauf_id": "lauf-001",
    }

    store.speichere_modulzustand("server_analysis", modulzustand)
    geladen = store.lade_modulzustand("server_analysis")

    assert geladen["serverlisten"][0]["servername"] == "srv-01"
    assert geladen["rollen"]["srv-01"] == ["APP"]
    assert geladen["ausgabepfade"]["analyse_report"] == "docs/a.md"
    assert geladen["letzter_exportpfad"] == "docs/a.md"
    assert geladen["letzte_export_lauf_id"] == "lauf-001"


def test_onboarding_status_wird_robust_geladen_und_gespeichert(tmp_path: Path) -> None:
    """Onboarding-Status soll inklusive neuer Felder kompatibel persistiert werden."""
    store = GUIStateStore(tmp_path / "gui_state.json")

    store.speichere_onboarding_status(
        {
            "onboarding_abgeschlossen": True,
            "onboarding_version": "1.2.3",
            "erststart_zeitpunkt": "2026-03-04T12:00:00",
        }
    )

    geladen = store.lade_onboarding_status()

    assert geladen["onboarding_abgeschlossen"] is True
    assert geladen["onboarding_version"] == "1.2.3"
    assert geladen["erststart_zeitpunkt"] == "2026-03-04T12:00:00"
    assert "letzter_abschluss_zeitpunkt" in geladen


def test_installer_modulzustand_schema_bleibt_stabil() -> None:
    """Der Installer-Zustand soll ein klares, erweitertes Basisschema liefern."""
    zustand = erstelle_installer_modulzustand(
        installiert=True,
        version="2.1.0",
        zeitpunkt="2026-05-06T10:11:12",
        bericht_pfad="logs/install_report.md",
    )

    assert zustand == {
        "installiert": True,
        "version": "2.1.0",
        "zeitpunkt": "2026-05-06T10:11:12",
        "bericht_pfad": "logs/install_report.md",
    }


def test_onboarding_status_migration_setzt_erststart_schema_stabil(tmp_path: Path) -> None:
    """Legacy-Onboardingdaten werden auf das aktuelle Erststart-Schema migriert."""
    store = GUIStateStore(tmp_path / "gui_state.json")
    store.speichere_gesamtzustand({
        "onboarding": {"onboarding_abgeschlossen": False, "onboarding_version": "0.9.0"},
        "modules": {},
    })

    geladen = store.lade_onboarding_status()

    assert geladen["onboarding_schema_version"] == 2
    assert geladen["onboarding_status"] == "ausstehend"
    assert geladen["abbruch_zeitpunkt"] == ""


def test_onboarding_status_migration_markiert_abbruch_konsistent(tmp_path: Path) -> None:
    """Ist ein Abbruchzeitpunkt vorhanden, bleibt der Modus eindeutig abgebrochen."""
    store = GUIStateStore(tmp_path / "gui_state.json")
    store.speichere_onboarding_status({"abbruch_zeitpunkt": "2026-07-01T08:30:00"})

    geladen = store.lade_onboarding_status()

    assert geladen["onboarding_abgeschlossen"] is False
    assert geladen["onboarding_status"] == "abgebrochen"
