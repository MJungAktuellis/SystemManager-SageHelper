"""Tests für die Update-Strategie inklusive Datensicherung."""

from __future__ import annotations

from pathlib import Path

from systemmanager_sagehelper.installation_state import InstallationsPruefung
from systemmanager_sagehelper.update_strategy import ermittle_update_kontext, sichere_persistente_daten_vor_update


def test_ermittle_update_kontext_erkennt_neuere_zielversion() -> None:
    """Bei installierter Altversion muss ein Update als erforderlich markiert werden."""
    kontext = ermittle_update_kontext(
        InstallationsPruefung(installiert=True, erkannte_version="1.0.0"),
        ziel_version="1.2.0",
    )

    assert kontext.modus == "maintenance"
    assert kontext.update_erforderlich is True


def test_sicherung_persistenter_daten_vor_update(tmp_path: Path) -> None:
    """Vor einem Update sollen Konfiguration, Logs und Reports in ein Backup kopiert werden."""
    (tmp_path / "config").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "docs").mkdir()

    (tmp_path / "config" / "gui_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "logs" / "app.log").write_text("ok", encoding="utf-8")
    (tmp_path / "docs" / "serverbericht.md").write_text("# report", encoding="utf-8")

    kontext = ermittle_update_kontext(
        InstallationsPruefung(installiert=True, erkannte_version="1.0.0"),
        ziel_version="2.0.0",
    )
    ergebnis = sichere_persistente_daten_vor_update(tmp_path, update_kontext=kontext)

    assert ergebnis.durchgefuehrt is True
    assert ergebnis.backup_root is not None
    assert (ergebnis.backup_root / "config" / "gui_state.json").exists()
    assert (ergebnis.backup_root / "logs" / "app.log").exists()
    assert (ergebnis.backup_root / "reports" / "serverbericht.md").exists()
    assert ergebnis.migrationslog_pfad is not None
    assert ergebnis.migrationslog_pfad.exists()
