"""Tests für Parser-Helfer der CLI."""

from __future__ import annotations

import unittest

from systemmanager_sagehelper.cli import _parse_deklarationen, _parse_discovery_range_text, _parse_liste, baue_parser


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

    def test_parse_discovery_range_text_liest_mehrbereich(self) -> None:
        segment = _parse_discovery_range_text("192.168.10.5-25")
        self.assertEqual("192.168.10", segment.basis)
        self.assertEqual(5, segment.start)
        self.assertEqual(25, segment.ende)

    def test_baue_parser_enthaelt_multi_range_und_seed_optionen(self) -> None:
        parser = baue_parser()
        args = parser.parse_args([
            "scan",
            "--discover-range",
            "192.168.10.1-10",
            "--discover-seed",
            "srv-01",
            "--discover-seeds-from-ad-dns",
        ])

        self.assertEqual(["192.168.10.1-10"], args.discover_range)
        self.assertEqual(["srv-01"], args.discover_seed)
        self.assertTrue(args.discover_seeds_from_ad_dns)


if __name__ == "__main__":
    unittest.main()
