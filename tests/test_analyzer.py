"""Tests für robuste Serveranalyse und Portprüfung."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from systemmanager_sagehelper.analyzer import (
    _klassifiziere_anwendungen,
    _normalisiere_rollen,
    analysiere_server,
    analysiere_mehrere_server,
    schlage_rollen_per_portsignatur_vor,
)
from systemmanager_sagehelper.models import ServerZiel


class TestAnalyzer(unittest.TestCase):
    """Prüft Fehlerpfade und Rollenlogik der Analyse."""

    def test_rollen_werden_normalisiert_und_duplikate_entfernt(self) -> None:
        rollen = _normalisiere_rollen([" app ", "SQL", "sql", "", " ctx "])
        self.assertEqual(["APP", "SQL", "CTX"], rollen)

    def test_klassifizierung_von_sage_partner_und_ssms(self) -> None:
        sage, partner, ssms = _klassifiziere_anwendungen(
            [
                "Sage 100 9.0",
                "Contoso CRM Connector 2.1",
                "SQL Server Management Studio 19",
            ]
        )
        self.assertEqual("Sage 100 9.0", sage)
        self.assertIn("Contoso CRM Connector 2.1", partner)
        self.assertEqual("SQL Server Management Studio 19", ssms)

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


    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.1"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=False)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    def test_mehrserveranalyse_uebernimmt_eine_gemeinsame_lauf_id(
        self,
        _sock_mock,
        _port_mock,
        _dns_mock,
    ) -> None:
        ziele = [
            ServerZiel(name="srv-01", rollen=["APP"]),
            ServerZiel(name="srv-02", rollen=["SQL"]),
        ]
        ergebnisse = analysiere_mehrere_server(ziele, lauf_id="lauf-test-001")

        self.assertEqual(2, len(ergebnisse))
        self.assertTrue(all(ergebnis.lauf_id == "lauf-test-001" for ergebnis in ergebnisse))


    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", side_effect=[True, False])
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[object()])
    def test_schnellprofil_liefert_rollenvorschlag(self, _sock_mock, _port_mock) -> None:
        rollen = schlage_rollen_per_portsignatur_vor("srv-sql")
        self.assertIn("SQL", rollen)

    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.1"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=False)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    def test_rollenquelle_aus_serverziel_wird_uebernommen(self, _sock_mock, _port_mock, _dns_mock) -> None:
        ergebnis = analysiere_server(
            ServerZiel(
                name="srv-app-01",
                rollen=["APP"],
                rollenquelle="nachträglich geändert",
                auto_rollen=["SQL"],
                manuell_ueberschrieben=True,
            )
        )
        self.assertEqual("nachträglich geändert", ergebnis.rollenquelle)
        self.assertEqual(["SQL"], ergebnis.auto_rollen)
        self.assertTrue(ergebnis.manuell_ueberschrieben)


if __name__ == "__main__":
    unittest.main()
