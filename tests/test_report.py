"""Tests für Markdown-Rendering."""

import unittest
from datetime import datetime

from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus
from systemmanager_sagehelper.report import render_markdown


class TestReport(unittest.TestCase):
    """Prüft die Markdown-Ausgabe auf zentrale Inhalte."""

    def test_render_markdown_enthaelt_server_port_und_systeminfos(self) -> None:
        ergebnis = AnalyseErgebnis(
            server="srv-app-01",
            zeitpunkt=datetime(2026, 1, 1, 10, 30, 0),
            lauf_id="lauf-20260101-103000-abcd1234",
            rollen=["APP"],
            betriebssystem="Windows",
            os_version="2022",
            cpu_logische_kerne=8,
            cpu_modell="Xeon",
            sage_version="Sage 100 9.0",
            management_studio_version="SQL Server Management Studio 19",
            partner_anwendungen=["Contoso CRM Connector"],
            installierte_anwendungen=["Sage 100 9.0", "Contoso CRM Connector"],
            ports=[PortStatus(port=3389, offen=True, bezeichnung="RDP")],
        )

        md = render_markdown([ergebnis])

        self.assertIn("## Server: srv-app-01", md)
        self.assertIn("3389 (RDP): ✅ offen", md)
        self.assertIn("CPU (logische Kerne): 8", md)
        self.assertIn("Sage-Version: Sage 100 9.0", md)
        self.assertIn("Lauf-ID: lauf-20260101-103000-abcd1234", md)


if __name__ == "__main__":
    unittest.main()
