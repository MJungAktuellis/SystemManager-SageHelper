"""Tests für Installationsschutz in Launcher und direkten Moduleinstiegen."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import doc_generator
import folder_manager
import gui_manager
import server_analysis_gui
from systemmanager_sagehelper.installation_state import InstallationsPruefung, verarbeite_installations_guard
from systemmanager_sagehelper.models import DiscoveryErgebnis


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
    gui.shell = SimpleNamespace(zeige_warnung=Mock(), setze_status=Mock())

    erlaubt = gui._installation_erforderlich_dialog("Serveranalyse")

    assert erlaubt is False
    gui.shell.zeige_warnung.assert_not_called()
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

    monkeypatch.setattr(folder_manager, "start_gui", ordner_start)
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


def test_onboarding_guard_startet_wizard_bei_offenem_status(monkeypatch) -> None:
    """Beim Erststart soll der Launcher den Onboarding-Wizard automatisch planen."""

    class _Store:
        def __init__(self) -> None:
            self.gespeichert = None

        def lade_onboarding_status(self):
            return {
                "onboarding_abgeschlossen": False,
                "onboarding_version": "1.0.0",
                "erststart_zeitpunkt": "",
            }

        def speichere_onboarding_status(self, status):
            self.gespeichert = status

    aufrufe: list[tuple[int, object]] = []

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.state_store = _Store()
    gui.shell = SimpleNamespace(setze_status=Mock())
    gui._onboarding_controller = SimpleNamespace(starte_wizard=Mock())
    gui.master = SimpleNamespace(after=lambda delay, callback: aufrufe.append((delay, callback)))

    status = gui._initialisiere_onboarding_status()
    gui._onboarding_aktiv = not status.get("onboarding_abgeschlossen", False)
    gui._pruefe_onboarding_guard()

    assert gui.state_store.gespeichert is not None
    assert gui.state_store.gespeichert["erststart_zeitpunkt"]
    assert len(aufrufe) == 1


def test_onboarding_guard_ignoriert_abgeschlossenen_status() -> None:
    """Ist das Onboarding abgeschlossen, darf kein Wizard geplant werden."""

    class _Store:
        def lade_onboarding_status(self):
            return {
                "onboarding_abgeschlossen": True,
                "onboarding_version": "1.0.0",
                "erststart_zeitpunkt": "2026-01-01T00:00:00",
            }

        def speichere_onboarding_status(self, status):
            raise AssertionError("Speichern darf hier nicht ausgelöst werden")

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.state_store = _Store()
    gui.shell = SimpleNamespace(setze_status=Mock())
    gui._onboarding_controller = SimpleNamespace(starte_wizard=Mock())
    gui.master = SimpleNamespace(after=Mock())

    status = gui._initialisiere_onboarding_status()
    gui._onboarding_aktiv = not status.get("onboarding_abgeschlossen", False)
    gui._pruefe_onboarding_guard()

    gui.master.after.assert_not_called()
    gui.shell.setze_status.assert_not_called()


class _StatusVar:
    """Leichtgewichtiger Ersatz für tk.StringVar in isolierten Unit-Tests."""

    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _ButtonVar:
    """Testdouble für Buttons, der configure-Parameter speichert."""

    def __init__(self) -> None:
        self.config: dict[str, str] = {}

    def configure(self, **kwargs) -> None:
        self.config.update(kwargs)


def test_installationskarte_zeigt_update_aktion_bei_installiertem_system() -> None:
    """Bei installierter Umgebung muss die Primäraktion auf Wartung/Update wechseln."""
    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui._karten_buttons = {"installation": _ButtonVar()}
    gui._karten_titel = {"installation": _StatusVar()}
    gui._karten_beschreibung = {"installation": _StatusVar()}
    gui._karten_experten_buttons = {"installation": _ButtonVar()}

    gui._aktualisiere_installationskarte(True, True)

    assert gui._karten_buttons["installation"].config["text"] == "Update / Wartung prüfen"
    assert gui._karten_titel["installation"].value == "Update & Wartung"
    assert gui._karten_experten_buttons["installation"].config["state"] == "normal"

def test_dashboard_installationsstatus_nutzt_marker_pruefung_mit_versionsinfo(monkeypatch) -> None:
    """Dashboard soll primär die Installationsprüfung und ergänzend GUI-State nutzen."""
    monkeypatch.setattr(
        gui_manager,
        "pruefe_installationszustand",
        lambda: InstallationsPruefung(installiert=True, erkannte_version="1.9.0"),
    )

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.state_store = SimpleNamespace(
        lade_gesamtzustand=lambda: {
            "modules": {
                "installer": {"installiert": True, "version": "2.0.0"},
                "server_analysis": {},
                "folder_manager": {},
                "doc_generator": {},
            }
        }
    )
    gui._karten_status = {
        "installation": _StatusVar(),
        "serveranalyse": _StatusVar(),
        "ordnerverwaltung": _StatusVar(),
        "dokumentation": _StatusVar(),
    }

    gui._aktualisiere_dashboard_status()

    assert gui._karten_status["installation"].value.startswith("Status: Installiert (2.0.0)")


def test_dashboard_installationsstatus_zeigt_teilweise_konfiguration_ohne_marker(monkeypatch) -> None:
    """Ist nur der GUI-State gesetzt, soll das Dashboard eine Teilkonfiguration signalisieren."""
    monkeypatch.setattr(
        gui_manager,
        "pruefe_installationszustand",
        lambda: InstallationsPruefung(installiert=False, gruende=["Marker fehlt"]),
    )

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.state_store = SimpleNamespace(
        lade_gesamtzustand=lambda: {
            "modules": {
                "installer": {"installiert": True, "version": "2.0.0"},
                "server_analysis": {},
                "folder_manager": {},
                "doc_generator": {},
            }
        }
    )
    gui._karten_status = {
        "installation": _StatusVar(),
        "serveranalyse": _StatusVar(),
        "ordnerverwaltung": _StatusVar(),
        "dokumentation": _StatusVar(),
    }

    gui._aktualisiere_dashboard_status()

    assert gui._karten_status["installation"].value == "Status: Teilweise installiert (Prüfung erforderlich)"


def test_onboarding_discovery_parse_gueltiger_bereich() -> None:
    """Der Discovery-Parser soll Basis plus Start/Ende korrekt übernehmen."""
    bereiche, gespeichert = gui_manager.OnboardingController._parse_discovery_eingabe("192.168.0", "1", "30")
    basis, start, ende = bereiche[0]

    assert basis == "192.168.0"
    assert start == 1
    assert ende == 30
    assert gespeichert == "192.168.0.1-30"

    bereiche_kurz, gespeichert_kurz = gui_manager.OnboardingController._parse_discovery_eingabe("192.168.0.10-25", "", "")
    basis_kurz, start_kurz, ende_kurz = bereiche_kurz[0]
    assert basis_kurz == "192.168.0"
    assert start_kurz == 10
    assert ende_kurz == 25
    assert gespeichert_kurz == "192.168.0.10-25"


def test_onboarding_discovery_parse_cidr_mapped_auf_discovery_bereiche() -> None:
    """CIDR-Eingaben sollen in wiederverwendbare Basis-Start-Ende-Bereiche zerlegt werden."""
    bereiche, gespeichert = gui_manager.OnboardingController._parse_discovery_eingabe("192.168.1.0/24", "", "")

    assert bereiche == [("192.168.1", 1, 254)]
    assert gespeichert == "192.168.1.0/24"


def test_onboarding_discovery_parse_vertauschte_grenzen() -> None:
    """Vertauschte Grenzen sollen mit verständlicher Fehlermeldung abgewiesen werden."""
    try:
        gui_manager.OnboardingController._parse_discovery_eingabe("192.168.0", "30", "1")
        raise AssertionError("Es hätte eine ValueError ausgelöst werden müssen")
    except ValueError as exc:
        assert "Start darf nicht größer als Ende sein" in str(exc)
        assert "192.168.0" in str(exc)


def test_onboarding_discovery_parse_ungueltiges_format() -> None:
    """Ungültige Formate sollen klare Beispiele in der Fehlermeldung enthalten."""
    try:
        gui_manager.OnboardingController._parse_discovery_eingabe("192.168", "1", "30")
        raise AssertionError("Es hätte eine ValueError ausgelöst werden müssen")
    except ValueError as exc:
        assert "Ungültiges Format für die Netzwerkerkennung" in str(exc)
        assert "192.168.0.0/24" in str(exc)
        assert "192.168.0.1-30" in str(exc)


def test_onboarding_liest_lokale_ipv4_konfiguration_unix(monkeypatch) -> None:
    """Lokale Interface-Daten sollen zu IPv4/Masken-Paaren aufgelöst werden."""
    ip_output = "2: eth0    inet 192.168.50.23/24 brd 192.168.50.255 scope global dynamic eth0\n"

    monkeypatch.setattr(gui_manager.os, "name", "posix", raising=False)

    def fake_check_output(command, text=True, stderr=None):  # noqa: ANN001,ANN201
        if command[:3] == ["ip", "-o", "-f"]:
            return ip_output
        raise FileNotFoundError

    monkeypatch.setattr(gui_manager.subprocess, "check_output", fake_check_output)

    konfigurationen = gui_manager.OnboardingController._sammle_lokale_ipv4_konfigurationen()

    assert konfigurationen == [("192.168.50.23", "255.255.255.0")]


def test_onboarding_auto_scanbereich_aus_netzkonfiguration() -> None:
    """Der Standardpfad soll einen Scanbereich ohne manuelle Eingabe ableiten."""
    controller = object.__new__(gui_manager.OnboardingController)

    class _Var:
        def __init__(self) -> None:
            self.value = ""

        def set(self, value: str) -> None:
            self.value = value

    controller._scanbereich_var = _Var()
    controller._sammle_lokale_ipv4_konfigurationen = lambda: [("10.10.2.11", "255.255.255.0")]

    bereiche, gespeichert = controller._ermittle_automatischen_scanbereich()

    assert bereiche == [("10.10.2", 1, 254)]
    assert gespeichert == "10.10.2.1-254"
    assert "10.10.2.0/24" in controller._scanbereich_var.value


def test_erststart_haelt_dashboard_gesperrt_bis_onboarding_abschluss() -> None:
    """Beim Erststart darf kein parallel nutzbares Dashboard aufgebaut werden."""

    gui = object.__new__(gui_manager.SystemManagerGUI)
    gui.state_store = SimpleNamespace(lade_onboarding_status=lambda: {"onboarding_abgeschlossen": False})
    gui._dashboard_gebaut = False
    gui._onboarding_aktiv = True
    gui._baue_dashboard = Mock()
    gui._onboarding_controller = SimpleNamespace(starte_wizard=Mock())
    gui.master = SimpleNamespace(after=Mock())

    gui._pruefe_onboarding_guard()

    gui._baue_dashboard.assert_not_called()
    assert gui._dashboard_gebaut is False
    gui.master.after.assert_called_once()


def test_onboarding_discovery_harmonisiert_rollenableitung_und_metadaten(monkeypatch) -> None:
    """Onboarding soll dieselbe Discovery-Heuristik wie die Haupt-GUI nutzen."""

    treffer = [
        DiscoveryErgebnis(
            hostname="srv-sql",
            ip_adresse="10.0.0.10",
            erreichbar=True,
            erkannte_dienste=["1433"],
            vertrauensgrad=0.91,
            rollenhinweise=["sql_instanz:mssqlserver"],
            namensquelle="dns",
        ),
        DiscoveryErgebnis(
            hostname="srv-app",
            ip_adresse="10.0.0.11",
            erreichbar=True,
            erkannte_dienste=["5985"],
            vertrauensgrad=0.66,
            rollenhinweise=["app_portsignatur"],
            namensquelle="ad",
        ),
        DiscoveryErgebnis(
            hostname="srv-ctx",
            ip_adresse="10.0.0.12",
            erreichbar=True,
            erkannte_dienste=["3389"],
            vertrauensgrad=0.82,
            rollenhinweise=["ctx_remote_dienst:termservice"],
            namensquelle="reverse_dns",
        ),
        DiscoveryErgebnis(
            hostname="srv-dc",
            ip_adresse="10.0.0.13",
            erreichbar=True,
            erkannte_dienste=["389"],
            vertrauensgrad=0.88,
            rollenhinweise=["dc_remote_dienst:netlogon"],
            namensquelle="dns",
        ),
        DiscoveryErgebnis(
            hostname="srv-mix",
            ip_adresse="10.0.0.14",
            erreichbar=False,
            erkannte_dienste=["3389"],
            vertrauensgrad=0.41,
            rollenhinweise=["sql_remote_dienst:mssqlserver", "dc_remote_dienst:netlogon"],
            namensquelle=None,
        ),
    ]

    monkeypatch.setattr(gui_manager, "entdecke_server_ergebnisse", lambda **_kwargs: treffer)

    controller = object.__new__(gui_manager.OnboardingController)
    controller.server_zeilen = []
    controller.gui = SimpleNamespace(modulzustand={})
    controller._ist_schritt_freigeschaltet = lambda _schritt: True
    controller._setze_aktuellen_schritt = lambda _schritt: None
    controller._ermittle_discovery_bereiche_fuer_schritt_1 = lambda: ([("10.0.0", 1, 20)], "10.0.0.1-20")
    controller._setze_status = lambda _text: None
    controller._markiere_schritt = lambda *args, **kwargs: None

    controller.schritt_discovery()

    assert [zeile.servername for zeile in controller.server_zeilen] == ["srv-sql", "srv-app", "srv-ctx", "srv-dc", "srv-mix"]
    assert [zeile.auto_rolle for zeile in controller.server_zeilen] == ["SQL", "APP", "CTX", "DC", "SQL, CTX, DC"]
    assert controller.server_zeilen[0].namensquelle == "dns"
    assert controller.server_zeilen[4].namensquelle == "nicht auflösbar"
    assert controller.server_zeilen[0].erreichbarkeitsstatus == "erreichbar (hoch)"
    assert controller.server_zeilen[1].erreichbarkeitsstatus == "erreichbar (mittel)"
    assert controller.server_zeilen[4].erreichbarkeitsstatus == "nicht erreichbar (niedrig)"
    assert controller.server_zeilen[4].rollenhinweise == ("sql_remote_dienst:mssqlserver", "dc_remote_dienst:netlogon")
    assert controller.server_zeilen[4].erreichbar is False
