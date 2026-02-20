"""Tests für Hilfsfunktionen der Mehrserver-GUI."""

from __future__ import annotations

from datetime import datetime

from server_analysis_gui import (
    DiscoveryTabellenTreffer,
    ServerTabellenZeile,
    _baue_serverziele,
    _deklarationszusammenfassung,
    _detailzeilen,
    _filter_discovery_treffer,
    _kurzstatus,
    _rollen_aus_discovery_treffer,
    _rollenquelle_fuer_zeile,
)
from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus


def test_baue_serverziele_mit_rollenabbildung() -> None:
    """Die Rollen sollen direkt aus dem Zeilenmodell übernommen werden."""
    zeilen = [
        ServerTabellenZeile(servername="srv-app-01", app=True, sql=False, ctx=False),
        ServerTabellenZeile(servername="srv-sql-01", app=False, sql=True, ctx=True, dc=True),
    ]

    ziele = _baue_serverziele(zeilen)

    assert len(ziele) == 2
    assert ziele[0].name == "srv-app-01"
    assert ziele[0].rollen == ["APP"]
    assert ziele[1].rollen == ["SQL", "CTX", "DC"]


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
    assert "srv-sql-01 | Rollen: SQL | Quelle: Netzwerkerkennung | Rollenquelle: automatisch erkannt" in zusammenfassung


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
        rollenhinweise=("sql_instanz:mssqlserver",),
    )
    dc_treffer = DiscoveryTabellenTreffer(
        hostname="srv-dc-01",
        ip_adresse="10.0.0.50",
        erreichbar=True,
        dienste="53, 389",
        vertrauensgrad=0.8,
        rollenhinweise=("dc_remote_dienst:netlogon",),
    )
    nur_app = DiscoveryTabellenTreffer(
        hostname="srv-02",
        ip_adresse="10.0.0.11",
        erreichbar=True,
        dienste="-",
        vertrauensgrad=0.2,
    )

    assert _rollen_aus_discovery_treffer(sql_ctx) == ["SQL", "CTX"]
    assert _rollen_aus_discovery_treffer(dc_treffer) == ["DC"]
    assert _rollen_aus_discovery_treffer(nur_app) == ["APP"]


def test_rollenableitung_sql_ohne_1433_durch_instanzhinweis() -> None:
    """SQL soll auch ohne Port 1433 erkannt werden, wenn belastbare Hinweise vorliegen."""
    nur_sql_hinweis = DiscoveryTabellenTreffer(
        hostname="srv-sql-browser",
        ip_adresse="10.0.0.12",
        erreichbar=True,
        dienste="1434",
        vertrauensgrad=0.6,
        rollenhinweise=("sql_instanz:sage", "sql_remote_dienst:sqlbrowser"),
    )
    assert _rollen_aus_discovery_treffer(nur_sql_hinweis) == ["SQL"]


def test_rollenableitung_gemischte_rollen() -> None:
    """Bei gemischten Hinweisen sollen mehrere Rollen gleichzeitig vorgeschlagen werden."""
    gemischt = DiscoveryTabellenTreffer(
        hostname="srv-mix-01",
        ip_adresse="10.0.0.13",
        erreichbar=True,
        dienste="3389",
        vertrauensgrad=0.7,
        rollenhinweise=("sql_remote_dienst:mssqlserver", "dc_remote_dienst:netlogon"),
    )
    assert _rollen_aus_discovery_treffer(gemischt) == ["SQL", "CTX", "DC"]


def test_executive_summary_aggregiert_rollen_ports_und_warnungen() -> None:
    """Die Executive Summary soll zentrale Kennzahlen konsistent zusammenfassen."""
    from server_analysis_gui import _baue_executive_summary

    ergebnisse = [
        AnalyseErgebnis(
            server="srv-01",
            zeitpunkt=datetime.now(),
            rollen=["SQL", "APP"],
            ports=[
                PortStatus(port=1433, offen=True, bezeichnung="MSSQL"),
                PortStatus(port=3389, offen=False, bezeichnung="RDP"),
            ],
            hinweise=["Hinweis A"],
        ),
        AnalyseErgebnis(
            server="srv-02",
            zeitpunkt=datetime.now(),
            rollen=["CTX", "DC"],
            ports=[PortStatus(port=135, offen=True, bezeichnung="RPC")],
            hinweise=[],
        ),
    ]

    summary = _baue_executive_summary(ergebnisse)

    assert any("Analysierte Server: 2" in zeile for zeile in summary)
    assert any("SQL=1" in zeile and "APP=1" in zeile and "CTX=1" in zeile and "DC=1" in zeile for zeile in summary)
    assert any("Offene kritische Ports: 2" in zeile for zeile in summary)
    assert any("Warnungen/Hinweise gesamt: 2" in zeile for zeile in summary)


def test_analyse_starten_erzeugt_bericht_und_zeigt_verweis(monkeypatch) -> None:
    """Nach erfolgreicher Analyse soll ein Bericht erzeugt und als Verweis sichtbar werden."""
    from server_analysis_gui import MehrserverAnalyseGUI

    class _FakeVar:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    class _FakeTree:
        def __init__(self) -> None:
            self.children: list[str] = []
            self.status_updates: dict[tuple[str, str], str] = {}

        def get_children(self, _root: str = "") -> list[str]:
            return list(self.children)

        def delete(self, _item_id: str) -> None:
            return

        def set(self, item_id: str, column: str, value: str) -> None:
            self.status_updates[(item_id, column)] = value

    class _FakeSummaryLabel:
        def __init__(self) -> None:
            self.text = ""

        def configure(self, *, text: str) -> None:
            self.text = text

    class _FakeShell:
        def __init__(self) -> None:
            self.lauf_id_var = _FakeVar("lauf-001")
            self.logs: list[str] = []
            self.status = ""
            self.erfolg_anzeigen = False

        def bestaetige_aktion(self, _titel: str, _nachricht: str) -> bool:
            return True

        def setze_lauf_id(self, lauf_id: str) -> None:
            self.lauf_id_var.set(lauf_id)

        def setze_status(self, status: str) -> None:
            self.status = status

        def logge_meldung(self, text: str) -> None:
            self.logs.append(text)

        def zeige_fehler(self, *_args) -> None:
            raise AssertionError("Bei Erfolg darf kein Fehlerdialog erscheinen")

        def zeige_warnung(self, *_args) -> None:
            raise AssertionError("Bei Erfolg darf kein Warnungsdialog erscheinen")

        def zeige_erfolg(self, *_args) -> None:
            self.erfolg_anzeigen = True

    gui = MehrserverAnalyseGUI.__new__(MehrserverAnalyseGUI)
    gui._zeilen_nach_id = {
        "row-1": ServerTabellenZeile(servername="srv-01", app=True, sql=False, ctx=False, status="bereit")
    }
    gui.tree = _FakeTree()
    gui.tree_ergebnisse = _FakeTree()
    gui.lbl_executive_summary = _FakeSummaryLabel()
    gui._ausgabe_pfad = _FakeVar("docs/test_report.md")
    gui._report_verweis_var = _FakeVar("")
    gui._letzter_export_pfad = ""
    gui._letzter_exportzeitpunkt = ""
    gui._letzte_export_lauf_id = ""
    gui._letzte_ergebnisse = []
    gui.shell = _FakeShell()
    gui.master = type("Master", (), {"update_idletasks": staticmethod(lambda: None)})()
    gui.speichern = lambda: None
    gui._zeige_ergebnisse_aufklappbar = lambda _ergebnisse: None

    ergebnis = AnalyseErgebnis(
        server="srv-01",
        zeitpunkt=datetime.now(),
        rollen=["APP"],
        ports=[PortStatus(port=1433, offen=True, bezeichnung="MSSQL")],
    )

    monkeypatch.setattr("server_analysis_gui.erstelle_lauf_id", lambda: "lauf-001")
    monkeypatch.setattr("server_analysis_gui.setze_lauf_id", lambda _lauf_id: None)
    monkeypatch.setattr("server_analysis_gui.analysiere_mehrere_server", lambda _ziele, lauf_id=None: [ergebnis])
    monkeypatch.setattr(
        "server_analysis_gui._schreibe_analyse_report",
        lambda _ergebnisse, _pfad: ("docs/test_report.md", "2026-01-02T03:04:05"),
    )

    gui.analyse_starten()

    assert gui._report_verweis_var.get().startswith("Letzter Analysebericht: docs/test_report.md")
    assert "Lauf-ID: lauf-001" in gui._report_verweis_var.get()
    assert gui.shell.erfolg_anzeigen is True
    assert any("Analysebericht erstellt: docs/test_report.md" in eintrag for eintrag in gui.shell.logs)


def test_filter_discovery_treffer_mit_standardfilter_auf_erreichbarkeit() -> None:
    """Nicht erreichbare Treffer bleiben standardmäßig ausgeblendet."""
    treffer = [
        DiscoveryTabellenTreffer(
            hostname="srv-app-01",
            ip_adresse="10.0.0.21",
            erreichbar=True,
            dienste="1433",
            vertrauensgrad=0.9,
        ),
        DiscoveryTabellenTreffer(
            hostname="srv-rdns-only",
            ip_adresse="10.0.0.22",
            erreichbar=False,
            dienste="-",
            vertrauensgrad=0.1,
        ),
        DiscoveryTabellenTreffer(
            hostname="srv-offline",
            ip_adresse="10.0.0.23",
            erreichbar=False,
            dienste="3389",
            vertrauensgrad=0.3,
        ),
    ]

    nur_erreichbare = _filter_discovery_treffer(treffer, filtertext="", nur_erreichbare=True)
    alle = _filter_discovery_treffer(treffer, filtertext="", nur_erreichbare=False)

    assert [item.hostname for item in nur_erreichbare] == ["srv-app-01"]
    assert [item.hostname for item in alle] == ["srv-app-01", "srv-rdns-only", "srv-offline"]
