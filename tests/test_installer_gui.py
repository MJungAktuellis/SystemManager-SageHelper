"""Tests für den Installations-Wizard und seine Navigationslogik."""

from __future__ import annotations

from pathlib import Path

from systemmanager_sagehelper import installer_gui


class _FakeVar:
    """Minimale Tk-Variable für Headless-Tests."""

    def __init__(self, value=None) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWindow:
    """Leichter Fensterersatz ohne echtes Tk-Backend."""

    def transient(self, _master) -> None:
        return

    def grab_set(self) -> None:
        return

    def geometry(self, _value: str) -> None:
        return

    def minsize(self, _x: int, _y: int) -> None:
        return

    def protocol(self, _name: str, _callback) -> None:
        return


class _FakeFrame:
    def __init__(self, _parent=None, **_kwargs) -> None:
        return

    def pack(self, **_kwargs) -> None:
        return


class _FakeButton:
    """Button-Dummy, der zuletzt gesetzte Werte für Assertions speichert."""

    def __init__(self, _parent=None, **kwargs) -> None:
        self.configs = dict(kwargs)

    def pack(self, **_kwargs) -> None:
        return

    def config(self, **kwargs) -> None:
        self.configs.update(kwargs)


class _FakeGuiShell:
    """Erfasst die Konstruktorparameter von GuiShell."""

    letzte_kwargs: dict[str, object] | None = None

    def __init__(self, _master, **kwargs) -> None:
        _FakeGuiShell.letzte_kwargs = kwargs
        self.content_frame = object()

    def setze_lauf_id(self, _lauf_id: str) -> None:
        return

    def setze_status(self, _text: str) -> None:
        return

    def logge_meldung(self, _text: str, *, technisch: bool = False) -> None:
        return

    def logge_fehler(self, _text: str) -> None:
        return


def test_installer_deaktiviert_globale_shell_aktionen(monkeypatch) -> None:
    """Der Wizard soll nur seine schrittspezifische Navigation anzeigen."""

    monkeypatch.setattr(installer_gui, "GuiShell", _FakeGuiShell)
    monkeypatch.setattr(installer_gui.tk, "Toplevel", lambda _master: _FakeWindow())
    monkeypatch.setattr(installer_gui.tk, "Tk", type("_DummyTk", (), {}))
    monkeypatch.setattr(installer_gui.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(installer_gui.tk, "BooleanVar", _FakeVar)
    monkeypatch.setattr(installer_gui.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(installer_gui.ttk, "Button", _FakeButton)
    monkeypatch.setattr(installer_gui, "erstelle_lauf_id", lambda: "lauf-test")
    monkeypatch.setattr(installer_gui, "erstelle_standard_komponenten", lambda _root: {})
    monkeypatch.setattr(installer_gui.InstallerWizardGUI, "_render_schritt", lambda self: None)

    installer_gui.InstallerWizardGUI(master=object(), source_root=Path("."), target_root=Path("."))

    assert _FakeGuiShell.letzte_kwargs is not None
    assert _FakeGuiShell.letzte_kwargs["show_actions"] is False
    assert _FakeGuiShell.letzte_kwargs["kurze_endnutzerhinweise"] is True


def test_navigation_verwendet_eine_einheitliche_button_logik() -> None:
    """Zurück/Weiter/Starten/Schließen sollen konsistent je Schritt gesteuert werden."""

    wizard = installer_gui.InstallerWizardGUI.__new__(installer_gui.InstallerWizardGUI)
    wizard.schritte = [
        installer_gui.WizardSchritt("willkommen", "Willkommen"),
        installer_gui.WizardSchritt("pfad_optionen", "Pfad"),
        installer_gui.WizardSchritt("komponenten", "Komponenten"),
        installer_gui.WizardSchritt("fortschritt", "Fortschritt"),
        installer_gui.WizardSchritt("abschluss", "Abschluss"),
    ]
    wizard.btn_zurueck = _FakeButton()
    wizard.btn_weiter = _FakeButton()
    wizard.installation_laueft = False
    wizard.mode = "install"
    wizard._weiter = lambda: None
    wizard._starte_installation = lambda: None
    wizard._beenden = lambda: None

    wizard.aktiver_schritt = 0
    wizard._aktualisiere_navigation()
    assert wizard.btn_zurueck.configs["state"] == "disabled"
    assert wizard.btn_weiter.configs["text"] == "Weiter"

    wizard.aktiver_schritt = 2
    wizard._aktualisiere_navigation()
    assert wizard.btn_weiter.configs["text"] == "Installation starten"

    wizard.aktiver_schritt = 4
    wizard._aktualisiere_navigation()
    assert wizard.btn_zurueck.configs["state"] == "disabled"
    assert wizard.btn_weiter.configs["text"] == "Schließen"
