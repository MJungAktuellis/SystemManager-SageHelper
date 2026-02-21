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

            self.assertEqual("install_engine.log", log_datei.name)
            self.assertEqual("logs", log_datei.parent.name)
            self.assertTrue(log_datei.parent.exists())

    def test_ermittle_beschreibbare_log_datei_nutzt_fallback_bei_permission_error(self) -> None:
        """Bei fehlenden Rechten muss ein benutzerschreibbarer Fallback genutzt werden."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            fake_localappdata = repo_root / "localappdata"

            original_open = Path.open

            def fake_open(path_obj: Path, *args: object, **kwargs: object):
                # Simuliert ein nicht beschreibbares Installationsziel.
                if path_obj == repo_root / "logs" / installer.INSTALLER_ENGINE_LOGDATEI:
                    raise PermissionError("Zugriff verweigert")
                return original_open(path_obj, *args, **kwargs)

            with (
                patch.dict("os.environ", {"LOCALAPPDATA": str(fake_localappdata)}, clear=False),
                patch("pathlib.Path.open", autospec=True, side_effect=fake_open),
            ):
                initialisierung = installer.ermittle_beschreibbare_log_datei(repo_root)

        erwarteter_fallback = fake_localappdata / "SystemManager-SageHelper" / "logs" / installer.INSTALLER_ENGINE_LOGDATEI
        self.assertTrue(initialisierung.verwendet_fallback)
        self.assertEqual(erwarteter_fallback, initialisierung.log_datei)
        self.assertIsNotNone(initialisierung.hinweis)

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

    def test_schreibe_installationsreport_enthaelt_desktop_status_abschnitt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            report_datei = installer.schreibe_installationsreport(
                repo_root,
                ergebnisse=[],
                auswahl={"voraussetzungen": True},
                desktop_verknuepfung_status="Admin-Start-Desktop-Verknüpfung: Erfolgreich erstellt (C:/Users/Public/Desktop/SystemManager-SageHelper.lnk)",
            )

            report_inhalt = report_datei.read_text(encoding="utf-8")

        self.assertIn("## Desktop-Verknüpfung", report_inhalt)
        self.assertIn("Admin-Start-Desktop-Verknüpfung: Erfolgreich erstellt", report_inhalt)
        self.assertIn("**Einstiegspfad:** CLI", report_inhalt)

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
            (scripts_dir / "start_systemmanager_gui_admin.ps1").write_text("Write-Host admin\n", encoding="utf-8")

            with patch(
                "systemmanager_sagehelper.installer.erstelle_windows_desktop_verknuepfung",
                return_value=Path("C:/Users/Public/Desktop/SystemManager-SageHelper.lnk"),
            ) as shortcut_mock:
                shortcut = installer.erstelle_desktop_verknuepfung_fuer_python_installation(repo_root)

        self.assertEqual(Path("C:/Users/Public/Desktop/SystemManager-SageHelper.lnk"), shortcut)
        shortcut_mock.assert_called_once()


    def test_validiere_quellpfad_prueft_installationsstruktur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            quell_root = Path(tmp_dir)
            (quell_root / "src" / "systemmanager_sagehelper").mkdir(parents=True, exist_ok=True)
            (quell_root / "src" / "systemmanager_sagehelper" / "installer.py").write_text("# test", encoding="utf-8")
            (quell_root / "scripts").mkdir(parents=True, exist_ok=True)
            (quell_root / "scripts" / "install.py").write_text("# test", encoding="utf-8")

            gueltig, _ = installer.validiere_quellpfad(quell_root)

        self.assertTrue(gueltig)

    def test_kopiere_installationsquellen_kopiert_zentrale_ressourcen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            basis = Path(tmp_dir)
            quell_root = basis / "quelle"
            ziel_root = basis / "ziel"
            (quell_root / "src" / "systemmanager_sagehelper").mkdir(parents=True, exist_ok=True)
            (quell_root / "scripts").mkdir(parents=True, exist_ok=True)
            (quell_root / "src" / "systemmanager_sagehelper" / "installer.py").write_text("# test", encoding="utf-8")
            (quell_root / "scripts" / "install.py").write_text("# test", encoding="utf-8")
            (quell_root / "requirements.txt").write_text("pytest", encoding="utf-8")

            kopiert = installer.kopiere_installationsquellen(quell_root, ziel_root)
            self.assertTrue((ziel_root / "src").exists())
            self.assertTrue((ziel_root / "scripts").exists())
            self.assertTrue((ziel_root / "requirements.txt").exists())
            self.assertTrue(kopiert)


    def test_richte_tool_dateien_und_launcher_ein_erstellt_gui_und_cli_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            installer.richte_tool_dateien_und_launcher_ein(repo_root)

            gui_launcher = repo_root / "scripts" / "start_systemmanager_gui.bat"
            admin_gui_launcher = repo_root / "scripts" / "start_systemmanager_gui_admin.ps1"
            cli_launcher = repo_root / "scripts" / "start_systemmanager_cli.bat"
            kompat_launcher = repo_root / "scripts" / "start_systemmanager.bat"

            self.assertTrue(gui_launcher.exists())
            self.assertTrue(admin_gui_launcher.exists())
            self.assertTrue(cli_launcher.exists())
            self.assertTrue(kompat_launcher.exists())

            self.assertIn("%APP_ROOT%\\src\\gui_manager.py", gui_launcher.read_text(encoding="utf-8"))
            self.assertIn("Start-Process -FilePath 'powershell.exe'", admin_gui_launcher.read_text(encoding="utf-8"))
            self.assertIn('set "PYTHONPATH=%APP_ROOT%\\src;%PYTHONPATH%"', cli_launcher.read_text(encoding="utf-8"))
            self.assertIn("python -m systemmanager_sagehelper %*", cli_launcher.read_text(encoding="utf-8"))
            self.assertIn("start_systemmanager.bat gui", kompat_launcher.read_text(encoding="utf-8"))

    def test_initialisiere_laufzeitordner_legt_standardordner_an_und_verifiziert_schreibbarkeit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            angelegte_ordner = installer.initialisiere_laufzeitordner(repo_root)
            erfolgreich, nachricht = installer.verifiziere_laufzeitordner(repo_root)

        self.assertEqual({"logs", "docs", "config"}, {pfad.name for pfad in angelegte_ordner})
        self.assertTrue(erfolgreich)
        self.assertIn("vorhanden und beschreibbar", nachricht)


if __name__ == "__main__":
    unittest.main()
