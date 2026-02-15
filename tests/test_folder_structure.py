"""Tests für Strukturprüfung und Ordneranlage."""

import tempfile
import unittest
from pathlib import Path

from systemmanager_sagehelper.folder_structure import ermittle_fehlende_ordner, lege_ordner_an


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


if __name__ == "__main__":
    unittest.main()
