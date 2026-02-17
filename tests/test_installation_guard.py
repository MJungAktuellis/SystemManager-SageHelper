"""Tests für Installationsschutz in Launcher und direkten Moduleinstiegen."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import doc_generator
import folder_manager
import gui_manager
import server_analysis_gui
from systemmanager_sagehelper.installation_state import InstallationsPruefung, verarbeite_installations_guard


def test_guard_akzeptiert_installierte_umgebung_ohne_nebenwirkungen() -> None:
    """Bei gültiger Installation darf der Guard ohne Dialoge passieren."""
    fehler = Mock()
    rueckfrage = Mock()

    erlaubt = verarbeite_installations_guard(
        InstallationsPruefung(installiert=True),
        modulname="Serveranalyse",
        fehlermeldung_fn=fehler,
        installationsfrage_fn=rueckfrage,
    )

    assert erlaubt is True
    fehler.assert_not_called()
    rueckfrage.assert_not_called()


def test_guard_blockiert_und_startet_installation_bei_bestaetigung() -> None:
    """Bei fehlender Installation soll der Workflow auf Wunsch direkt gestartet werden."""
    fehler = Mock()

    erlaubt = verarbeite_installations_guard(
        InstallationsPruefung(installiert=False, gruende=["Marker fehlt"]),
        modulname="Dokumentation",
        fehlermeldung_fn=fehler,
        installationsfrage_fn=lambda _: True,
        installation_starten_fn=lambda: 0,
    )

    assert erlaubt is True
    fehler.assert_called_once()


def test_launcher_guard_zeigt_hinweis_und_startet_installation(monkeypatch) -> None:
    """Der Launcher soll gesperrte Module erklären und die Installation anbieten."""
    pruefung = InstallationsPruefung(installiert=False, gruende=["Marker fehlt"])
    monkeypatch.setattr(gui_manager, "pruefe_installationszustand", lambda: pruefung)
    monkeypatch.setattr(gui_manager.messagebox, "askyesno", lambda *args, **kwargs: True)

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.master = object()
    gui.installieren = Mock()
    gui.shell = SimpleNamespace(zeige_warnung=Mock())

    erlaubt = gui._installation_erforderlich_dialog("Serveranalyse")

    assert erlaubt is False
    gui.shell.zeige_warnung.assert_called_once()
    gui.installieren.assert_called_once()


def test_launcher_installieren_oeffnet_installer_wizard(monkeypatch) -> None:
    """Die Installationsaktion im Launcher soll den GUI-Wizard starten."""
    wizard_start = Mock()
    monkeypatch.setattr(gui_manager, "InstallerWizardGUI", wizard_start)

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.master = object()
    gui._starte_neuen_lauf = Mock(return_value="lauf-123")
    gui._nach_installation = Mock()
    gui.shell = SimpleNamespace(
        bestaetige_aktion=Mock(return_value=True),
        setze_status=Mock(),
        logge_meldung=Mock(),
    )

    gui.installieren()

    gui.shell.bestaetige_aktion.assert_called_once()
    wizard_start.assert_called_once()
    assert wizard_start.call_args.kwargs["on_finished"] is not None


def test_serveranalyse_main_startet_gui_nur_bei_freigabe(monkeypatch) -> None:
    """Direkter GUI-Entry darf nur nach erfolgreichem Guard laufen."""
    start = Mock()
    monkeypatch.setattr(server_analysis_gui, "start_gui", start)
    monkeypatch.setattr(server_analysis_gui, "verarbeite_installations_guard", lambda *args, **kwargs: False)

    server_analysis_gui.main()
    start.assert_not_called()

    monkeypatch.setattr(server_analysis_gui, "verarbeite_installations_guard", lambda *args, **kwargs: True)
    server_analysis_gui.main()
    assert start.call_count == 1


def test_folder_und_doku_main_respektieren_guard(monkeypatch) -> None:
    """Direkte Modulstarts sollen bei gesperrter Installation nicht ausführen."""
    ordner_start = Mock()
    doku_start = Mock()

    monkeypatch.setattr(folder_manager, "pruefe_und_erstelle_struktur", ordner_start)
    monkeypatch.setattr(doc_generator, "erstelle_dokumentation", doku_start)

    monkeypatch.setattr(folder_manager, "verarbeite_installations_guard", lambda *args, **kwargs: False)
    monkeypatch.setattr(doc_generator, "verarbeite_installations_guard", lambda *args, **kwargs: False)

    folder_manager.main()
    doc_generator.main()

    ordner_start.assert_not_called()
    doku_start.assert_not_called()

    monkeypatch.setattr(folder_manager, "verarbeite_installations_guard", lambda *args, **kwargs: True)
    monkeypatch.setattr(doc_generator, "verarbeite_installations_guard", lambda *args, **kwargs: True)

    folder_manager.main()
    doc_generator.main()

    ordner_start.assert_called_once()
    doku_start.assert_called_once()
