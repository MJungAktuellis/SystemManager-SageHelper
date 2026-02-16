"""Tests für den Python-Installationslauncher in scripts/install.py."""

from __future__ import annotations

import builtins
import importlib.util
import unittest
from pathlib import Path
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

    def test_frage_ja_nein_nutzt_standardwert_bei_eof_true(self) -> None:
        with patch.object(builtins, "input", side_effect=EOFError):
            self.assertTrue(install_script._frage_ja_nein("Test", standard=True))

    def test_frage_ja_nein_nutzt_standardwert_bei_eof_false(self) -> None:
        with patch.object(builtins, "input", side_effect=EOFError):
            self.assertFalse(install_script._frage_ja_nein("Test", standard=False))


if __name__ == "__main__":
    unittest.main()
