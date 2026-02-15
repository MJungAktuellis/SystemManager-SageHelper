"""Tests für Parser-Helfer der CLI."""

from __future__ import annotations

import unittest

from systemmanager_sagehelper.cli import _parse_deklarationen, _parse_liste


class TestCli(unittest.TestCase):
    """Validiert die robuste Verarbeitung von Listenparametern."""

    def test_parse_liste_entfernt_leerwerte_und_duplikate(self) -> None:
        ergebnis = _parse_liste(" srv1, ,srv2,srv1 ")
        self.assertEqual(["srv1", "srv2"], ergebnis)

    def test_parse_liste_mit_uppercase(self) -> None:
        ergebnis = _parse_liste("app, SQL, app", to_upper=True)
        self.assertEqual(["APP", "SQL"], ergebnis)

    def test_parse_deklarationen_parst_rollen_je_server(self) -> None:
        ergebnis = _parse_deklarationen("srv1=sql,app;srv2=ctx")
        self.assertEqual({"srv1": ["SQL", "APP"], "srv2": ["CTX"]}, ergebnis)


if __name__ == "__main__":
    unittest.main()
