"""Tests für robuste Serveranalyse und Portprüfung."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from systemmanager_sagehelper.analyzer import (
    DiscoveryKonfiguration,
    RemoteAbrufFehler,
    _klassifiziere_anwendungen,
    _normalisiere_rollen,
    entdecke_server_ergebnisse,
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


    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.1"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=False)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    def test_hinweis_bei_remote_timeout_wird_klassifiziert(self, _sock_mock, _port_mock, _dns_mock) -> None:
        provider = Mock()
        provider.ist_verfuegbar.return_value = True
        provider.lese_systemdaten.side_effect = RemoteAbrufFehler("[TIMEOUT]", "Zeitüberschreitung bei WinRM-Verbindung.")

        ergebnis = analysiere_server(ServerZiel(name="srv-timeout", rollen=["APP"]), remote_provider=provider)

        self.assertTrue(any(hinweis.startswith("[TIMEOUT]") for hinweis in ergebnis.hinweise))

    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.1"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", side_effect=[True, False, False])
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    def test_hinweis_freigegebene_relevante_ports(self, _sock_mock, _port_mock, _dns_mock) -> None:
        ergebnis = analysiere_server(ServerZiel(name="srv-sql-01", rollen=["SQL"]))
        self.assertTrue(any("Freigegebene/relevante Ports" in h and "1433" in h for h in ergebnis.hinweise))


    def test_discovery_invalid_range_wirft_value_error(self) -> None:
        with self.assertRaises(ValueError):
            entdecke_server_ergebnisse(basis="192.168", start=1, ende=2)

    @patch("systemmanager_sagehelper.analyzer._resolve_reverse_dns", return_value="srv-dns-only.local")
    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.5"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=False)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[])
    @patch("systemmanager_sagehelper.analyzer._ping_host", return_value=False)
    def test_discovery_dns_only_treffer_wird_verworfen(
        self,
        _ping_mock,
        _sock_mock,
        _port_mock,
        _dns_mock,
        _reverse_mock,
    ) -> None:
        ergebnisse = entdecke_server_ergebnisse(
            basis="10.0.0",
            start=5,
            ende=5,
            konfiguration=DiscoveryKonfiguration(nutze_reverse_dns=True, max_worker=1),
        )

        self.assertEqual([], ergebnisse)

    @patch("systemmanager_sagehelper.analyzer._resolve_reverse_dns", return_value="srv-duplikat.local")
    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.0.8"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=True)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[object()])
    @patch("systemmanager_sagehelper.analyzer._ping_host", return_value=True)
    def test_discovery_duplikate_werden_dedupliziert(
        self,
        _ping_mock,
        _sock_mock,
        _port_mock,
        _dns_mock,
        _reverse_mock,
    ) -> None:
        ergebnisse = entdecke_server_ergebnisse(
            basis="10.0.0",
            start=8,
            ende=9,
            konfiguration=DiscoveryKonfiguration(max_worker=2),
        )

        self.assertEqual(1, len(ergebnisse))
        self.assertEqual("srv-duplikat.local", ergebnisse[0].hostname)


    @patch("systemmanager_sagehelper.analyzer._resolve_reverse_dns", side_effect=["srv-10", "srv-10.domain.local"])
    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.2.10"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=True)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[object()])
    @patch("systemmanager_sagehelper.analyzer._ping_host", return_value=True)
    def test_discovery_dedupliziert_nach_normalisiertem_hostname_und_ip(
        self,
        _ping_mock,
        _sock_mock,
        _port_mock,
        _dns_mock,
        _reverse_mock,
    ) -> None:
        ergebnisse = entdecke_server_ergebnisse(
            basis="10.0.2",
            start=10,
            ende=11,
            konfiguration=DiscoveryKonfiguration(max_worker=2),
        )

        self.assertEqual(1, len(ergebnisse))
        self.assertEqual("10.0.2.10", ergebnisse[0].ip_adresse)

    @patch("systemmanager_sagehelper.analyzer._resolve_reverse_dns", return_value=None)
    @patch("systemmanager_sagehelper.analyzer._ermittle_ip_adressen", return_value=["10.0.1.7"])
    @patch("systemmanager_sagehelper.analyzer.pruefe_tcp_port", return_value=False)
    @patch("systemmanager_sagehelper.analyzer._ermittle_socket_kandidaten", return_value=[object()])
    @patch("systemmanager_sagehelper.analyzer._ping_host", return_value=False)
    def test_discovery_timeout_netz_liefert_keinen_treffer(
        self,
        _ping_mock,
        _sock_mock,
        _port_mock,
        _dns_mock,
        _reverse_mock,
    ) -> None:
        ergebnisse = entdecke_server_ergebnisse(
            basis="10.0.1",
            start=7,
            ende=7,
            konfiguration=DiscoveryKonfiguration(nutze_reverse_dns=False, max_worker=1),
        )

        self.assertEqual([], ergebnisse)


if __name__ == "__main__":
    unittest.main()
