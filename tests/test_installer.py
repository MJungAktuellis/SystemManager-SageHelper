"""Tests für den Installationskern."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from systemmanager_sagehelper import installer


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
        self.assertEqual(["python", "-m", "pip", "install", "-r", str(repo_root / "requirements.txt")], befehl)


if __name__ == "__main__":
    unittest.main()
