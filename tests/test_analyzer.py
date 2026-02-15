"""Tests für robuste Serveranalyse und Portprüfung."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from systemmanager_sagehelper.analyzer import _normalisiere_rollen, analysiere_server
from systemmanager_sagehelper.models import ServerZiel


class TestAnalyzer(unittest.TestCase):
    """Prüft Fehlerpfade und Rollenlogik der Analyse."""

    def test_rollen_werden_normalisiert_und_duplikate_entfernt(self) -> None:
        rollen = _normalisiere_rollen([" app ", "SQL", "sql", "", " ctx "])
        self.assertEqual(["APP", "SQL", "CTX"], rollen)

    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=[])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=False)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    def test_hinweis_bei_nicht_aufloesbarem_host(self, _sock_mock, _port_mock, _dns_mock) -> None:
        ergebnis = analysiere_server(ServerZiel(name="ungueltig.example.invalid", rollen=["APP"]))
        self.assertTrue(any("Hostname konnte nicht aufgelöst" in h for h in ergebnis.hinweise))

    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.1"])
    @patch(
        "systemmanager_sagehelper.analyzer.pruefe_tcp_port",
        side_effect=[True, False, False],
    )
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    def test_erwartete_rollen_warnung_wenn_portprofil_nicht_passt(
        self,
        _sock_mock,
        _port_mock,
        _dns_mock,
    ) -> None:
        ergebnis = analysiere_server(ServerZiel(name="srv-sql-01", rollen=["app", "SQL"]))
        self.assertTrue(
            any("nicht bestätigt" in hinweis and "APP" in hinweis for hinweis in ergebnis.hinweise)
        )


if __name__ == "__main__":
    unittest.main()
