"""Tests für Hilfsfunktionen der Mehrserver-GUI."""

from __future__ import annotations

from datetime import datetime

from server_analysis_gui import (
    DiscoveryTabellenTreffer,
    ServerTabellenZeile,
    _baue_serverziele,
    _deklarationszusammenfassung,
    _detailzeilen,
    _kurzstatus,
    _rollen_aus_discovery_treffer,
    _rollenquelle_fuer_zeile,
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
    assert "srv-app-01 | Rollen: APP | Quelle: manuell | Rollenquelle: manuell gesetzt" in zusammenfassung
    assert "srv-sql-01 | Rollen: SQL | Quelle: Discovery | Rollenquelle: automatisch erkannt" in zusammenfassung


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
    assert "Quelle:" in kurz
    assert "Offene Ports: 1433" in kurz
    assert any("SQL-Prüfung" in detail for detail in details)
    assert any("Remote-Ziel erkannt" in detail for detail in details)


def test_rollenquelle_fuer_discovery_und_manuelle_aenderung() -> None:
    """Die Rollenquelle soll Discovery und manuelle Anpassung differenzieren."""
    auto_zeile = ServerTabellenZeile(servername="srv-01", quelle="Discovery", auto_rolle="SQL")
    geaendert = ServerTabellenZeile(
        servername="srv-02",
        quelle="Discovery",
        auto_rolle="SQL",
        manuell_ueberschrieben=True,
    )

    assert _rollenquelle_fuer_zeile(auto_zeile) == "automatisch erkannt"
    assert _rollenquelle_fuer_zeile(geaendert) == "nachträglich geändert"


def test_rollenableitung_aus_discovery_diensten() -> None:
    """Discovery-Dienste sollen eine plausible Rollenvorbelegung liefern."""
    sql_ctx = DiscoveryTabellenTreffer(
        hostname="srv-01",
        ip_adresse="10.0.0.10",
        erreichbar=True,
        dienste="1433, 3389",
        vertrauensgrad=0.9,
    )
    nur_app = DiscoveryTabellenTreffer(
        hostname="srv-02",
        ip_adresse="10.0.0.11",
        erreichbar=True,
        dienste="-",
        vertrauensgrad=0.2,
    )

    assert _rollen_aus_discovery_treffer(sql_ctx) == ["SQL", "CTX"]
    assert _rollen_aus_discovery_treffer(nur_app) == ["APP"]
