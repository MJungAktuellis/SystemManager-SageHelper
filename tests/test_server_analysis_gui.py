"""Tests für Hilfsfunktionen der Mehrserver-GUI."""

from __future__ import annotations

from datetime import datetime

from server_analysis_gui import (
    ServerTabellenZeile,
    _baue_serverziele,
    _deklarationszusammenfassung,
    _detailzeilen,
    _kurzstatus,
)
from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus


def test_baue_serverziele_mit_rollenabbildung() -> None:
    """Die Rollen sollen direkt aus dem Zeilenmodell übernommen werden."""
    zeilen = [
        ServerTabellenZeile(servername="srv-app-01", app=True, sql=False, ctx=False),
        ServerTabellenZeile(servername="srv-sql-01", app=False, sql=True, ctx=True),
    ]

    ziele = _baue_serverziele(zeilen)

    assert len(ziele) == 2
    assert ziele[0].name == "srv-app-01"
    assert ziele[0].rollen == ["APP"]
    assert ziele[1].rollen == ["SQL", "CTX"]


def test_deklarationszusammenfassung_enthaelt_quelle_und_rollen() -> None:
    """Die Vorab-Zusammenfassung soll alle Kerndaten für die Freigabe enthalten."""
    zeilen = [
        ServerTabellenZeile(servername="srv-app-01", app=True, quelle="manuell"),
        ServerTabellenZeile(servername="srv-sql-01", app=False, sql=True, quelle="Discovery"),
    ]
    ziele = _baue_serverziele(zeilen)

    zusammenfassung = _deklarationszusammenfassung(ziele, zeilen)

    assert "So wurden die Server deklariert:" in zusammenfassung
    assert "srv-app-01 | Rollen: APP | Quelle: manuell" in zusammenfassung
    assert "srv-sql-01 | Rollen: SQL | Quelle: Discovery" in zusammenfassung


def test_kurzstatus_und_detailzeilen_rendert_serverbloecke() -> None:
    """Die neue Ergebnisansicht soll Kurzstatus und detailierte Unterpunkte bereitstellen."""
    ergebnis = AnalyseErgebnis(
        server="srv-sql-01",
        zeitpunkt=datetime.now(),
        rollen=["SQL"],
        ports=[PortStatus(port=1433, offen=True, bezeichnung="MSSQL")],
        hinweise=["Remote-Ziel erkannt"],
    )

    kurz = _kurzstatus(ergebnis)
    details = _detailzeilen(ergebnis)

    assert "Rollen: SQL" in kurz
    assert "Offene Ports: 1433" in kurz
    assert any("SQL-Prüfung" in detail for detail in details)
    assert any("Remote-Ziel erkannt" in detail for detail in details)
