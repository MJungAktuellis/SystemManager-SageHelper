"""Tests für den Installationskern."""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from systemmanager_sagehelper import installer
from systemmanager_sagehelper.installer_options import (
    InstallerOptionen,
    baue_inno_setup_parameter,
    mappe_inno_tasks,
)


class TestInstaller(unittest.TestCase):
    """Prüft zentrale Hilfsfunktionen des Installers."""

    def test_pruefe_werkzeug_ohne_pfad_liefert_nicht_gefunden(self) -> None:
        with patch("systemmanager_sagehelper.installer.ermittle_befehlspfad", return_value=None):
            status = installer.pruefe_werkzeug("git", ["git", "--version"])

        self.assertFalse(status.gefunden)
        self.assertEqual("git", status.name)

    def test_installiere_python_pakete_ohne_requirements_tut_nichts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch("systemmanager_sagehelper.installer.fuehre_installationsbefehl_aus") as run_mock:
                installer.installiere_python_pakete(repo_root)

        run_mock.assert_not_called()

    def test_installiere_python_pakete_mit_requirements_ruft_pip_auf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "requirements.txt").write_text("pytest\n", encoding="utf-8")

            with patch("systemmanager_sagehelper.installer.fuehre_installationsbefehl_aus") as run_mock:
                installer.installiere_python_pakete(repo_root, python_executable="python")

        run_mock.assert_called_once()
        befehl = run_mock.call_args.args[0]
        self.assertEqual(
            ["python", "-m", "pip", "install", "-r", str(repo_root / "requirements.txt")],
            befehl,
        )

    def test_ermittle_log_datei_legt_logs_ordner_an(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            log_datei = installer.ermittle_log_datei(repo_root)

            self.assertEqual("install_assistant.log", log_datei.name)
            self.assertEqual("logs", log_datei.parent.name)
            self.assertTrue(log_datei.parent.exists())

    def test_konfiguriere_logging_verwendet_datei_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            log_datei = installer.konfiguriere_logging(repo_root)
            logger = logging.getLogger()

            datei_handler = [
                handler
                for handler in logger.handlers
                if isinstance(handler, logging.FileHandler)
                and Path(handler.baseFilename) == log_datei
            ]

            self.assertTrue(datei_handler)

            for handler in datei_handler:
                logger.removeHandler(handler)
                handler.close()

    def test_validiere_auswahl_und_abhaengigkeiten_fehlt_abhaengigkeit(self) -> None:
        komponenten = {
            "python": installer.InstallationsKomponente(
                id="python",
                name="Python",
                default_aktiv=True,
                install_fn=lambda: "ok",
                verify_fn=lambda: (True, "ok"),
            ),
            "tool": installer.InstallationsKomponente(
                id="tool",
                name="Tool",
                default_aktiv=True,
                abhaengigkeiten=("python",),
                install_fn=lambda: "ok",
                verify_fn=lambda: (True, "ok"),
            ),
        }

        with self.assertRaises(installer.InstallationsFehler):
            installer.validiere_auswahl_und_abhaengigkeiten(
                komponenten,
                {"python": False, "tool": True},
            )

    def test_fuehre_installationsplan_aus_nutzt_feste_reihenfolge(self) -> None:
        aufruf_reihenfolge: list[str] = []

        def baue_komponente(komponenten_id: str) -> installer.InstallationsKomponente:
            return installer.InstallationsKomponente(
                id=komponenten_id,
                name=komponenten_id,
                default_aktiv=True,
                install_fn=lambda: aufruf_reihenfolge.append(komponenten_id) or "ok",
                verify_fn=lambda: (True, "ok"),
            )

        komponenten = {
            key: baue_komponente(key)
            for key in installer.STANDARD_REIHENFOLGE
        }

        ergebnisse = installer.fuehre_installationsplan_aus(
            komponenten,
            {key: True for key in installer.STANDARD_REIHENFOLGE},
        )

        self.assertEqual(installer.STANDARD_REIHENFOLGE, aufruf_reihenfolge)
        self.assertEqual(len(installer.STANDARD_REIHENFOLGE), len(ergebnisse))


    def test_pruefe_und_behebe_voraussetzungen_liefert_admin_fehler(self) -> None:
        with (
            patch("systemmanager_sagehelper.installer.ist_windows_system", return_value=True),
            patch("systemmanager_sagehelper.installer.hat_adminrechte", return_value=False),
        ):
            statusliste = installer.pruefe_und_behebe_voraussetzungen()

        self.assertEqual(installer.ErgebnisStatus.ERROR, statusliste[0].status)
        self.assertEqual("Administratorrechte", statusliste[0].pruefung)

    def test_pruefe_und_behebe_voraussetzungen_pip_ok(self) -> None:
        with (
            patch("systemmanager_sagehelper.installer.ist_windows_system", return_value=True),
            patch("systemmanager_sagehelper.installer.hat_adminrechte", return_value=True),
            patch(
                "systemmanager_sagehelper.installer.finde_kompatiblen_python_interpreter",
                return_value=[installer.sys.executable],
            ),
            patch("systemmanager_sagehelper.installer._pip_verfuegbar_fuer_interpreter", return_value=True),
        ):
            statusliste = installer.pruefe_und_behebe_voraussetzungen()

        self.assertTrue(
            any(
                eintrag.pruefung == "pip" and eintrag.status == installer.ErgebnisStatus.OK
                for eintrag in statusliste
            )
        )

    def test_mappe_inno_tasks_fuer_desktop_icon(self) -> None:
        optionen = InstallerOptionen(desktop_icon=True)
        self.assertEqual(["desktopicon"], mappe_inno_tasks(optionen))

    def test_baue_inno_setup_parameter_ohne_desktop_icon(self) -> None:
        optionen = InstallerOptionen(desktop_icon=False)
        self.assertEqual(["/MERGETASKS=!desktopicon"], baue_inno_setup_parameter(optionen))

    def test_erstelle_desktop_verknuepfung_fuer_python_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            scripts_dir = repo_root / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            (scripts_dir / "start_systemmanager.bat").write_text("@echo off\n", encoding="utf-8")

            with patch(
                "systemmanager_sagehelper.installer.erstelle_windows_desktop_verknuepfung",
                return_value=Path("C:/Users/Public/Desktop/SystemManager-SageHelper.lnk"),
            ) as shortcut_mock:
                shortcut = installer.erstelle_desktop_verknuepfung_fuer_python_installation(repo_root)

        self.assertEqual(Path("C:/Users/Public/Desktop/SystemManager-SageHelper.lnk"), shortcut)
        shortcut_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
