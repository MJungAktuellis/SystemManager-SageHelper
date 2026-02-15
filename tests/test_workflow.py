"""Tests für die End-to-End-Orchestrierung inkl. Fehlerfällen."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from systemmanager_sagehelper.models import AnalyseErgebnis, PortStatus, ServerZiel
from systemmanager_sagehelper.workflow import WorkflowSchritt, fuehre_standard_workflow_aus


def test_workflow_liefert_standardisierte_schritte_und_fortschritt(tmp_path: Path) -> None:
    """Der Workflow soll alle Schritte in fixer Reihenfolge und mit Progress-Events liefern."""
    progress_events: list[tuple[WorkflowSchritt, int, str]] = []

    analyse_ergebnis = AnalyseErgebnis(
        server="srv-app-01",
        zeitpunkt=datetime(2026, 1, 1, 10, 0, 0),
        rollen=["APP"],
        ports=[PortStatus(port=3389, offen=True, bezeichnung="RDP")],
    )

    with (
        patch("systemmanager_sagehelper.workflow.erzeuge_installationsbericht", return_value=[]),
        patch("systemmanager_sagehelper.workflow.analysiere_mehrere_server", return_value=[analyse_ergebnis]),
        patch("systemmanager_sagehelper.workflow.pruefe_und_erstelle_struktur", return_value=[]),
        patch(
            "systemmanager_sagehelper.workflow.erstelle_dokumentation",
            return_value=tmp_path / "docs" / "ServerDokumentation.md",
        ),
    ):
        ergebnis = fuehre_standard_workflow_aus(
            ziele=[ServerZiel(name="srv-app-01", rollen=["APP"])],
            basis_pfad=tmp_path / "SystemAG",
            report_pfad=tmp_path / "docs" / "bericht.md",
            logs_verzeichnis=tmp_path / "logs",
            docs_verzeichnis=tmp_path / "docs",
            lauf_id="lauf-1",
            progress=lambda s, p, t: progress_events.append((s, p, t)),
        )

    assert [s.schritt for s in ergebnis.schritte] == [
        WorkflowSchritt.INSTALLATION,
        WorkflowSchritt.ANALYSE,
        WorkflowSchritt.ORDNER_FREIGABEN,
        WorkflowSchritt.DOKUMENTATION,
    ]
    assert ergebnis.erfolgreich
    assert progress_events[0][1] == 10
    assert progress_events[-1][1] == 100


def test_workflow_markiert_freigabefehler_als_nicht_erfolgreich(tmp_path: Path) -> None:
    """Fehlgeschlagene Freigaben müssen den Gesamtworkflow sauber auf fehlerhaft setzen."""

    class _FakeFreigabe:
        def __init__(self, erfolg: bool) -> None:
            self.erfolg = erfolg

    analyse_ergebnis = AnalyseErgebnis(server="srv-01", zeitpunkt=datetime.now())

    with (
        patch("systemmanager_sagehelper.workflow.erzeuge_installationsbericht", return_value=[]),
        patch("systemmanager_sagehelper.workflow.analysiere_mehrere_server", return_value=[analyse_ergebnis]),
        patch("systemmanager_sagehelper.workflow.pruefe_und_erstelle_struktur", return_value=[_FakeFreigabe(False)]),
        patch(
            "systemmanager_sagehelper.workflow.erstelle_dokumentation",
            return_value=tmp_path / "docs" / "ServerDokumentation.md",
        ),
    ):
        ergebnis = fuehre_standard_workflow_aus(
            ziele=[ServerZiel(name="srv-01", rollen=["SQL"])],
            basis_pfad=tmp_path / "SystemAG",
            report_pfad=tmp_path / "docs" / "bericht.md",
            logs_verzeichnis=tmp_path / "logs",
            docs_verzeichnis=tmp_path / "docs",
        )

    assert not ergebnis.erfolgreich
    ordner_schritt = next(s for s in ergebnis.schritte if s.schritt == WorkflowSchritt.ORDNER_FREIGABEN)
    assert not ordner_schritt.erfolgreich
