"""Tests für Strukturprüfung, Kandidatensuche und Ordneranlage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from systemmanager_sagehelper.folder_structure import (
    ermittle_fehlende_ordner,
    finde_systemag_kandidaten,
    lege_ordner_an,
    pruefe_systemag_kandidaten,
)


class TestFolderStructure(unittest.TestCase):
    """Stellt sicher, dass fehlende Pfade erkannt und erstellt werden."""

    def test_fehlende_ordner_werden_angezeigt_und_angelegt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            basis = Path(tmp_dir) / "SystemAG"
            fehlend = ermittle_fehlende_ordner(basis)
            self.assertTrue(fehlend)

            lege_ordner_an(fehlend)
            erneut = ermittle_fehlende_ordner(basis)
            self.assertEqual([], erneut)

    def test_kandidatensuche_findet_systemag_ordner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)
            kandidat = home / "KundeA" / "SystemAG"
            kandidat.mkdir(parents=True)

            from unittest.mock import patch

            with patch("systemmanager_sagehelper.folder_structure.Path.home", return_value=home):
                gefunden = finde_systemag_kandidaten(max_tiefe=2)

            self.assertIn(kandidat, gefunden)

    def test_kandidatenanalyse_markiert_unvollstaendige_struktur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            kandidat = Path(tmp_dir) / "SystemAG"
            kandidat.mkdir(parents=True)

            analysen = pruefe_systemag_kandidaten([kandidat])
            self.assertEqual(1, len(analysen))
            self.assertFalse(analysen[0].ist_vollstaendig)
            self.assertTrue(analysen[0].fehlende_unterordner)


if __name__ == "__main__":
    unittest.main()
