"""Tests für den veralteten Legacy-Einstieg der Serverrollen-Analyse."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import server_roles_analysis


class TestServerRolesAnalysisLegacy(unittest.TestCase):
    """Stellt sicher, dass Legacy nur noch delegiert und keine Eigenlogik enthält."""

    def test_analyze_server_roles_delegiert_komplett_an_analyzer(self) -> None:
        """Der Legacy-Wrapper darf keine Dummy-Rollen mehr zurückgeben."""
        erwartete_nutzlast = {"server": "srv-a", "rollen": ["APP"]}

        with (
            patch("server_roles_analysis._protokolliere_und_warne_deprecation"),
            patch("server_roles_analysis.analysiere_mehrere_server", return_value=[object()]) as analyzer_mock,
            patch("server_roles_analysis.asdict", return_value=erwartete_nutzlast),
        ):
            ergebnis = server_roles_analysis.analyze_server_roles(["srv-a"], ["app"])

        analyzer_mock.assert_called_once()
        self.assertEqual([erwartete_nutzlast], ergebnis)

    def test_main_blockiert_standardmaessig_produktive_nutzung(self) -> None:
        """Ohne Wrapper-Flag muss der Legacy-Einstieg mit Exit-Code 1 enden."""
        with patch("server_roles_analysis._protokolliere_und_warne_deprecation"):
            self.assertEqual(1, server_roles_analysis.main([]))


if __name__ == "__main__":
    unittest.main()
