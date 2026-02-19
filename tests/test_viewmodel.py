"""Tests für die Transformationslogik AnalyseErgebnis -> Detailkarte."""

from __future__ import annotations

from datetime import datetime

from systemmanager_sagehelper.models import AnalyseErgebnis, DienstInfo, PortStatus, SoftwareInfo
from systemmanager_sagehelper.viewmodel import baue_server_detailkarte


def test_baue_server_detailkarte_mit_strukturierten_tabs() -> None:
    """Die Detailkarte soll Rollen, Ports/Dienste, Software und Empfehlungen trennen."""
    ergebnis = AnalyseErgebnis(
        server="srv-01",
        zeitpunkt=datetime(2026, 1, 1, 12, 0, 0),
        rollen=["APP"],
        rollenquelle="automatisch erkannt",
        betriebssystem="Windows Server",
        os_version="2022",
        ports=[PortStatus(port=3389, offen=False, bezeichnung="RDP")],
        dienste=[DienstInfo(name="MSSQLSERVER", status="running")],
        software=[SoftwareInfo(name="Sage 100", version="9.0")],
        hinweise=["Prüfung durch Admin empfohlen"],
        empfehlungen=["Firewall-Regel für RDP prüfen"],
    )

    karte = baue_server_detailkarte(ergebnis)

    assert karte.server == "srv-01"
    assert karte.rollen == ["APP"]
    assert any(eintrag.typ == "Port" and eintrag.status == "blockiert/unerreichbar" for eintrag in karte.ports_und_dienste)
    assert any(eintrag.typ == "Dienst" and eintrag.name == "MSSQLSERVER" for eintrag in karte.ports_und_dienste)
    assert "Sage 100 9.0" in karte.software
    assert any("Firewall-Regel" in eintrag for eintrag in karte.empfehlungen)
    assert "Prüfung durch Admin empfohlen" in karte.freitext_hinweise
