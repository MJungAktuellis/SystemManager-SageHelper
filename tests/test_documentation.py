"""Tests für das strukturierte Dokumentmodell in documentation.py."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from systemmanager_sagehelper.documentation import erstelle_dokumentation
from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus


def test_erstelle_dokumentation_loop_modus_nutzt_analyse_state(tmp_path: Path) -> None:
    """Loop-Modus soll kompakt rendern und Artefakte konsistent referenzieren."""
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "server_analysis.log").write_text("run_id=lauf-1\nTrace", encoding="utf-8")

    ergebnisse = [
        AnalyseErgebnis(
            server="srv-sql-01",
            zeitpunkt=datetime(2026, 1, 2, 11, 0, 0),
            lauf_id="lauf-1",
            rollen=["SQL"],
            ports=[PortStatus(port=1433, offen=False, bezeichnung="MSSQL")],
            hinweise=["Freigabe SystemAG$ fehlt"],
        )
    ]

    pfad = erstelle_dokumentation(
        str(logs),
        str(tmp_path / "docs"),
        analyse_ergebnisse=ergebnisse,
        berichtsmodus="kompakt",
        analysebericht_pfad="docs/serverbericht.md",
    )

    inhalt = pfad.read_text(encoding="utf-8")
    assert "Berichtsmodus: Kompaktbericht" in inhalt
    assert "## Zielgruppe: Drittuser" in inhalt
    assert "| P1 | srv-sql-01: Port 1433 (MSSQL) prüfen/freischalten |" in inhalt
    assert "Analysebericht: docs/serverbericht.md" in inhalt
    assert "Lauf-IDs: lauf-1" in inhalt
    assert "## Log-Anhang (Referenz)" in inhalt


def test_erstelle_dokumentation_vollmodus_enthaelt_befundkategorien(tmp_path: Path) -> None:
    """Vollmodus soll Befundkategorien vollständig ausgeben."""
    logs = tmp_path / "logs"
    logs.mkdir()

    ergebnisse = [
        AnalyseErgebnis(
            server="srv-app-01",
            zeitpunkt=datetime(2026, 1, 1, 10, 30, 0),
            lauf_id="lauf-2",
            rollen=["APP"],
            rollenquelle="manuell gesetzt",
            ports=[PortStatus(port=3389, offen=True, bezeichnung="RDP")],
            hinweise=["Zusätzlicher Treiber prüfen"],
        )
    ]

    pfad = erstelle_dokumentation(str(logs), str(tmp_path / "docs"), analyse_ergebnisse=ergebnisse, berichtsmodus="voll")
    inhalt = pfad.read_text(encoding="utf-8")

    assert "Berichtsmodus: Vollbericht" in inhalt
    assert "## Zielgruppe: Admin" in inhalt
    assert "### Befunde" in inhalt
    assert "#### Rollen" in inhalt
    assert "#### Ports" in inhalt
    assert "#### Freigaben" in inhalt
    assert "#### Hinweise" in inhalt
