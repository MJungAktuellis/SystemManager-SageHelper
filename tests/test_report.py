"""Tests für Markdown-Rendering."""

import unittest
from datetime import datetime

from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus
from systemmanager_sagehelper.report import render_markdown


class TestReport(unittest.TestCase):
    """Prüft die Markdown-Ausgabe auf zentrale Inhalte."""

    def test_render_markdown_enthaelt_server_und_portstatus(self) -> None:
        ergebnis = AnalyseErgebnis(
            server="srv-app-01",
            zeitpunkt=datetime(2026, 1, 1, 10, 30, 0),
            rollen=["APP"],
            betriebssystem="Windows",
            os_version="2022",
            ports=[PortStatus(port=3389, offen=True, bezeichnung="RDP")],
        )

        md = render_markdown([ergebnis])

        self.assertIn("## Server: srv-app-01", md)
        self.assertIn("3389 (RDP): ✅ offen", md)


if __name__ == "__main__":
    unittest.main()
