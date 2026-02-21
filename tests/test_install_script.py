"""Tests für den Python-Installationslauncher in scripts/install.py."""

from __future__ import annotations

import builtins
import importlib.util
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT_PATH = REPO_ROOT / "scripts" / "install.py"

_spec = importlib.util.spec_from_file_location("install_script", INSTALL_SCRIPT_PATH)
install_script = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(install_script)


class TestInstallScript(unittest.TestCase):
    """Prüft Interaktions- und CLI-Verhalten des Installationsscripts."""

    def test_parse_cli_args_aktiviert_non_interactive_flag(self) -> None:
        args = install_script.parse_cli_args(["--non-interactive"])
        self.assertTrue(args.non_interactive)

    def test_parse_cli_args_mode_standard_auto(self) -> None:
        args = install_script.parse_cli_args([])
        self.assertEqual("auto", args.mode)

    def test_parse_cli_args_desktop_icon_standardmaessig_aktiv(self) -> None:
        args = install_script.parse_cli_args([])
        self.assertTrue(args.desktop_icon)

    def test_parse_cli_args_deaktiviert_desktop_icon_per_flag(self) -> None:
        args = install_script.parse_cli_args(["--no-desktop-icon"])
        self.assertFalse(args.desktop_icon)

    def test_frage_ja_nein_nutzt_standardwert_bei_eof_true(self) -> None:
        with patch.object(builtins, "input", side_effect=EOFError):
            self.assertTrue(install_script._frage_ja_nein("Test", standard=True))

    def test_frage_ja_nein_nutzt_standardwert_bei_eof_false(self) -> None:
        with patch.object(builtins, "input", side_effect=EOFError):
            self.assertFalse(install_script._frage_ja_nein("Test", standard=False))

    def test_safe_print_cp1252_ersetzt_emojis_ohne_unicodefehler(self) -> None:
        """Stellt sicher, dass cp1252-Konsolen robust mit Emoji-Ausgaben umgehen.

        Hintergrund: In älteren Windows-Konsolen ist häufig cp1252 aktiv.
        Emojis sind dort nicht direkt darstellbar und müssen zuverlässig in
        einen ASCII-kompatiblen Fallback überführt werden.
        """

        class FakeStdout(io.StringIO):
            # Simuliert eine klassische Windows-Konsole mit cp1252-Codepage.
            encoding = "cp1252"

        fake_stdout = FakeStdout()
        with patch.object(install_script.sys, "stdout", fake_stdout):
            install_script._safe_print("Installationsstatus ✅ 🚀")

        self.assertIn("Installationsstatus", fake_stdout.getvalue())
        self.assertIn("? ?", fake_stdout.getvalue())

    def test_safe_print_ascii_fallback_wenn_stdout_schreiben_scheitert(self) -> None:
        """Prüft den finalen ASCII-Fallback bei Schreibproblemen der Konsole."""

        class ProblematischerStdout:
            # Simuliert eine defekte/inkonsistente Konsole mit cp1252-Codepage,
            # bei der das Schreiben zunächst einen UnicodeEncodeError wirft.
            encoding = "cp1252"

            def __init__(self) -> None:
                self._buffer: list[str] = []
                self._saw_first_error = False

            def write(self, text: str) -> int:
                if not self._saw_first_error:
                    self._saw_first_error = True
                    raise UnicodeEncodeError("cp1252", "✅", 0, 1, "cannot encode")
                self._buffer.append(text)
                return len(text)

            def flush(self) -> None:  # pragma: no cover - keine Logik, nur Print-Vertrag
                return None

            def getvalue(self) -> str:
                return "".join(self._buffer)

        stdout = ProblematischerStdout()
        with patch.object(install_script.sys, "stdout", stdout):
            install_script._safe_print("Installation ✅")

        self.assertIn("Installation ?", stdout.getvalue())


    def test_starte_gui_modus_liefert_exit_code_0_nur_bei_success(self) -> None:
        """Der GUI-Modus meldet nur bei erfolgreichem Wizard-Abschluss Exit 0."""

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "systemmanager_sagehelper.installer_gui":
                return SimpleNamespace(
                    starte_installer_wizard=lambda **_kwargs: SimpleNamespace(abschluss_status="success")
                )
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            exit_code = install_script._starte_gui_modus(Path("."), Path("./ziel"))

        self.assertEqual(0, exit_code)

    def test_starte_gui_modus_liefert_exit_code_1_bei_cancelled(self) -> None:
        """Ein geschlossenes GUI-Fenster ohne Installation muss Exit 1 liefern."""

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "systemmanager_sagehelper.installer_gui":
                return SimpleNamespace(
                    starte_installer_wizard=lambda **_kwargs: SimpleNamespace(abschluss_status="cancelled")
                )
            return original_import(name, *args, **kwargs)

        with (
            patch.object(builtins, "__import__", side_effect=fake_import),
            patch.object(install_script, "_safe_print") as safe_print_mock,
        ):
            exit_code = install_script._starte_gui_modus(Path("."), Path("./ziel"))

        self.assertEqual(1, exit_code)
        safe_print_mock.assert_called_with("[WARN] GUI-Wizard ohne Erfolg beendet: cancelled")

    def test_main_bricht_bei_permission_error_in_logging_klar_ab(self) -> None:
        """Logging-Rechtefehler werden explizit gemeldet statt still abzubrechen."""

        with (
            patch.object(
                install_script,
                "parse_cli_args",
                return_value=SimpleNamespace(
                    mode="cli",
                    non_interactive=True,
                    desktop_icon=False,
                    source=Path("."),
                    target=Path("./ziel"),
                ),
            ),
            patch.object(install_script, "validiere_quellpfad", return_value=(True, "ok")),
            patch.object(install_script, "konfiguriere_logging", side_effect=PermissionError("blocked")),
            patch.object(install_script, "_safe_print") as safe_print_mock,
        ):
            with self.assertRaises(SystemExit) as system_exit:
                install_script.main()

        self.assertEqual(1, system_exit.exception.code)
        safe_print_mock.assert_any_call("[ERROR] Logging konnte nicht initialisiert werden (fehlende Schreibrechte).")

    def test_main_non_interactive_verwendet_standardauswahl(self) -> None:
        """Deckt den Non-Interactive-Ausgabepfad im Hauptablauf mit Mocks ab."""

        komponenten = {"kern": SimpleNamespace(default_aktiv=True, name="Kernkomponente")}

        with (
            patch.object(install_script, "parse_cli_args", return_value=SimpleNamespace(mode="cli", non_interactive=True, desktop_icon=False, source=Path("."), target=Path("./ziel"))),
            patch.object(install_script, "validiere_quellpfad", return_value=(True, "ok")),
            patch.object(install_script, "konfiguriere_logging", return_value="install.log"),
            patch.object(install_script, "kopiere_installationsquellen"),
            patch.object(install_script, "erstelle_standard_komponenten", return_value=komponenten),
            patch.object(install_script, "drucke_voraussetzungsstatus"),
            patch.object(install_script, "drucke_statusbericht"),
            patch.object(install_script, "STANDARD_REIHENFOLGE", ["kern"]),
            patch.object(install_script, "validiere_auswahl_und_abhaengigkeiten") as validiere_mock,
            patch.object(install_script, "fuehre_installationsplan_aus", return_value=[]),
            patch.object(install_script, "schreibe_installationsreport", return_value="report.md") as report_mock,
            patch.object(install_script, "schreibe_installations_marker", return_value="installed.marker"),
            patch.object(install_script, "_safe_print") as safe_print_mock,
        ):
            install_script.main()

        validiere_mock.assert_called_once_with(komponenten, {"kern": True})
        report_mock.assert_called_once()
        self.assertEqual("Admin-Start-Desktop-Verknüpfung: Deaktiviert", report_mock.call_args.kwargs["desktop_verknuepfung_status"])
        self.assertEqual("cli", report_mock.call_args.kwargs["einstiegspfad"])
        safe_print_mock.assert_any_call("\n[INFO] Non-Interactive-Modus aktiv: Standardauswahl wird verwendet.")

    def test_main_auto_faellt_bei_gui_importfehler_auf_cli_zurueck(self) -> None:
        """Stellt sicher, dass Auto-Mode bei GUI-Importfehler robust auf CLI wechselt."""

        komponenten = {"kern": SimpleNamespace(default_aktiv=True, name="Kernkomponente")}

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "systemmanager_sagehelper.installer_gui":
                raise ImportError("GUI-Modul absichtlich nicht verfügbar")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(
                install_script,
                "parse_cli_args",
                return_value=SimpleNamespace(
                    mode="auto",
                    non_interactive=True,
                    desktop_icon=False,
                    source=Path("."),
                    target=Path("./ziel"),
                ),
            ),
            patch.object(install_script, "validiere_quellpfad", return_value=(True, "ok")),
            patch.object(install_script, "konfiguriere_logging", return_value="install.log"),
            patch.object(install_script, "kopiere_installationsquellen"),
            patch.object(install_script, "erstelle_standard_komponenten", return_value=komponenten),
            patch.object(install_script, "drucke_voraussetzungsstatus"),
            patch.object(install_script, "drucke_statusbericht"),
            patch.object(install_script, "STANDARD_REIHENFOLGE", ["kern"]),
            patch.object(install_script, "validiere_auswahl_und_abhaengigkeiten"),
            patch.object(install_script, "fuehre_installationsplan_aus", return_value=[]),
            patch.object(install_script, "schreibe_installationsreport", return_value="report.md") as report_mock,
            patch.object(install_script, "schreibe_installations_marker", return_value="installed.marker"),
            patch.object(install_script, "_safe_print") as safe_print_mock,
            patch.object(builtins, "__import__", side_effect=fake_import),
        ):
            install_script.main()

        self.assertEqual("cli", report_mock.call_args.kwargs["einstiegspfad"])
        safe_print_mock.assert_any_call("[INFO] Fallback auf CLI-Orchestrierung.")


if __name__ == "__main__":
    unittest.main()
