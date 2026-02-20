"""Tests für Markdown-Rendering inkl. stabiler Abschnittsreihenfolge."""

import unittest
from datetime import datetime

from systemmanager_sagehelper.models import (
    AnalyseErgebnis,
    CPUDetails,
    DotNetVersion,
    Kundenstammdaten,
    Netzwerkidentitaet,
    PortStatus,
)
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
            kundenstammdaten=Kundenstammdaten(kundennummer="K-123"),
            netzwerkidentitaet=Netzwerkidentitaet(hostname="srv-app-01", fqdn="srv-app-01.contoso.local", domain="contoso.local", ip_adressen=["10.0.0.10"]),
            cpu_details=CPUDetails(physische_kerne=4, logische_threads=8, takt_mhz=2800.0),
            dotnet_versionen=[DotNetVersion(produkt="NET Runtime", version="8.0.2")],
        )

        md = render_markdown([ergebnis], kunde="Contoso", umgebung="Produktion")

        self.assertIn("## Kopfbereich", md)
        self.assertIn("## Kundenblatt", md)
        self.assertIn("- Kundennummer: K-123", md)
        self.assertIn("## Serverübersicht", md)
        self.assertIn("## Detailblöcke je Server", md)
        self.assertIn("## Server: srv-app-01", md)
        self.assertIn("3389 (RDP): ✅ Erfolgreich: offen", md)
        self.assertIn("### FQDN", md)
        self.assertIn("### IP", md)
        self.assertIn("### Versionen", md)
        self.assertIn("### Pfade", md)
        self.assertIn("### Freigaben", md)

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
        self.assertIn("## Maßnahmen", md)
        self.assertIn("Port 1433 (MSSQL)", md)

    def test_snapshot_abschnittsreihenfolge_bleibt_stabil(self) -> None:
        """Sichert die Reihenfolge der Pflichtabschnitte gegen versehentliche Regressionen."""
        md = render_markdown([
            AnalyseErgebnis(server="srv-01", zeitpunkt=datetime(2026, 1, 2, 11, 0, 0))
        ])

        abschnitte = [
            "## Kopfbereich",
            "## Kundenblatt",
            "## Zusammenfassung",
            "## Serverübersicht",
            "## Befunde",
            "## Auswirkungen",
            "## Maßnahmen",
            "## Artefakte",
        ]
        positionen = [md.index(abschnitt) for abschnitt in abschnitte]
        self.assertEqual(positionen, sorted(positionen))


if __name__ == "__main__":
    unittest.main()
