"""Tests für Markdown-Rendering."""

import unittest
from datetime import datetime

from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus
from systemmanager_sagehelper.report import render_markdown


class TestReport(unittest.TestCase):
    """Prüft die Markdown-Ausgabe auf zentrale Inhalte."""

    def test_render_markdown_vollbericht_enthaelt_template_und_detailblock(self) -> None:
        ergebnis = AnalyseErgebnis(
            server="srv-app-01",
            zeitpunkt=datetime(2026, 1, 1, 10, 30, 0),
            lauf_id="lauf-20260101-103000-abcd1234",
            rollen=["APP"],
            rollenquelle="manuell gesetzt",
            auto_rollen=["APP"],
            manuell_ueberschrieben=False,
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

        md = render_markdown([ergebnis], kunde="Contoso", umgebung="Produktion")

        self.assertIn("## Kopfbereich", md)
        self.assertIn("- Kunde: Contoso", md)
        self.assertIn("- Umgebung: Produktion", md)
        self.assertIn("- Template-Version: 1.0", md)
        self.assertIn("## Serverliste", md)
        self.assertIn("## Detailblöcke je Server", md)
        self.assertIn("## Server: srv-app-01", md)
        self.assertIn("3389 (RDP): ✅ Erfolgreich: offen", md)
        self.assertIn("CPU (logische Kerne): 8", md)
        self.assertIn("Sage-Version: Sage 100 9.0", md)
        self.assertIn("Lauf-ID: lauf-20260101-103000-abcd1234", md)
        self.assertIn("Rollenquelle: manuell gesetzt", md)
        self.assertIn("### Freigegebene/relevante Ports", md)

    def test_render_markdown_kurzbericht_laesst_detailblock_aus(self) -> None:
        ergebnis = AnalyseErgebnis(
            server="srv-sql-01",
            zeitpunkt=datetime(2026, 1, 2, 11, 0, 0),
            lauf_id="lauf-20260102-110000-efgh5678",
            rollen=["SQL"],
            ports=[PortStatus(port=1433, offen=False, bezeichnung="MSSQL")],
            hinweise=["SQL-Port ist derzeit nicht erreichbar"],
        )

        md = render_markdown([ergebnis], berichtsmodus="kurz")

        self.assertIn("- Berichtstyp: Kurzbericht für Loop", md)
        self.assertNotIn("## Detailblöcke je Server", md)
        self.assertIn("## Maßnahmen und offene Punkte", md)
        self.assertIn("Port 1433 (MSSQL)", md)


if __name__ == "__main__":
    unittest.main()
