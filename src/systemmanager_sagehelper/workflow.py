"""Orchestrierung des End-to-End-Ablaufs.

Ablauf: Installation -> Analyse -> Ordner/Freigaben -> Dokumentation.
Jeder Schritt liefert ein standardisiertes Ergebnisobjekt und kann Fortschritt
an einen Callback melden (GUI/CLI-kompatibel).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from .analyzer import analysiere_mehrere_server
from .documentation import erstelle_dokumentation
from .installer import erzeuge_installationsbericht
from .models import AnalyseErgebnis, ServerZiel
from .report import render_markdown
from .share_manager import FreigabeErgebnis, pruefe_und_erstelle_struktur


class WorkflowSchritt(Enum):
    """Definiert alle Schritte des orchestrierten Gesamtprozesses."""

    INSTALLATION = "installation"
    ANALYSE = "analyse"
    ORDNER_FREIGABEN = "ordner_freigaben"
    DOKUMENTATION = "dokumentation"


@dataclass
class SchrittErgebnis:
    """Einheitliches Ergebnis je Workflow-Schritt."""

    schritt: WorkflowSchritt
    erfolgreich: bool
    meldung: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class WorkflowErgebnis:
    """Gesamtergebnis eines Orchestrierungslaufs inkl. Einzelresultaten."""

    schritte: list[SchrittErgebnis] = field(default_factory=list)

    @property
    def erfolgreich(self) -> bool:
        """Workflow gilt nur als erfolgreich, wenn alle Schritte erfolgreich sind."""
        return all(s.erfolgreich for s in self.schritte)


ProgressCallback = Callable[[WorkflowSchritt, int, str], None]


def _melde(progress: ProgressCallback | None, schritt: WorkflowSchritt, prozent: int, nachricht: str) -> None:
    """Kapselt Fortschrittsmeldungen, damit CLI/GUI ohne Duplikate andocken können."""
    if progress is not None:
        progress(schritt, prozent, nachricht)


def _schritt_installation(progress: ProgressCallback | None) -> SchrittErgebnis:
    _melde(progress, WorkflowSchritt.INSTALLATION, 10, "Installationsstatus wird geprüft")
    statusliste = erzeuge_installationsbericht()
    gefunden = sum(1 for eintrag in statusliste if eintrag.gefunden)
    meldung = f"{gefunden}/{len(statusliste)} Werkzeuge verfügbar"
    _melde(progress, WorkflowSchritt.INSTALLATION, 25, meldung)
    return SchrittErgebnis(
        schritt=WorkflowSchritt.INSTALLATION,
        erfolgreich=True,
        meldung=meldung,
        details={"werkzeuge": [eintrag.__dict__ for eintrag in statusliste]},
    )


def _schritt_analyse(ziele: list[ServerZiel], lauf_id: str | None, progress: ProgressCallback | None) -> SchrittErgebnis:
    _melde(progress, WorkflowSchritt.ANALYSE, 40, "Serveranalyse wird gestartet")
    ergebnisse = analysiere_mehrere_server(ziele, lauf_id=lauf_id)
    _melde(progress, WorkflowSchritt.ANALYSE, 60, f"{len(ergebnisse)} Server analysiert")
    return SchrittErgebnis(
        schritt=WorkflowSchritt.ANALYSE,
        erfolgreich=True,
        meldung=f"Analyse abgeschlossen ({len(ergebnisse)} Server)",
        details={"analyse_ergebnisse": ergebnisse},
    )


def _schritt_ordner_und_freigaben(basis_pfad: Path, progress: ProgressCallback | None) -> SchrittErgebnis:
    _melde(progress, WorkflowSchritt.ORDNER_FREIGABEN, 70, "Ordner/Freigaben werden verarbeitet")
    freigaben = pruefe_und_erstelle_struktur(str(basis_pfad))
    erfolgreich = all(e.erfolg for e in freigaben)
    meldung = "Freigaben erfolgreich gesetzt" if erfolgreich else "Mindestens eine Freigabe fehlgeschlagen"
    _melde(progress, WorkflowSchritt.ORDNER_FREIGABEN, 85, meldung)
    return SchrittErgebnis(
        schritt=WorkflowSchritt.ORDNER_FREIGABEN,
        erfolgreich=erfolgreich,
        meldung=meldung,
        details={"freigaben": freigaben},
    )


def _schritt_dokumentation(
    analyse_ergebnisse: list[AnalyseErgebnis],
    report_pfad: Path,
    logs_verzeichnis: Path,
    docs_verzeichnis: Path,
    progress: ProgressCallback | None,
) -> SchrittErgebnis:
    _melde(progress, WorkflowSchritt.DOKUMENTATION, 90, "Markdown-Berichte werden erzeugt")
    report_pfad.parent.mkdir(parents=True, exist_ok=True)
    report_pfad.write_text(render_markdown(analyse_ergebnisse), encoding="utf-8")
    log_doku = erstelle_dokumentation(str(logs_verzeichnis), str(docs_verzeichnis))
    _melde(progress, WorkflowSchritt.DOKUMENTATION, 100, "Dokumentation abgeschlossen")
    return SchrittErgebnis(
        schritt=WorkflowSchritt.DOKUMENTATION,
        erfolgreich=True,
        meldung="Dokumentation erstellt",
        details={"analyse_report": str(report_pfad), "log_report": str(log_doku)},
    )


def fuehre_standard_workflow_aus(
    *,
    ziele: list[ServerZiel],
    basis_pfad: Path,
    report_pfad: Path,
    logs_verzeichnis: Path,
    docs_verzeichnis: Path,
    lauf_id: str | None = None,
    progress: ProgressCallback | None = None,
) -> WorkflowErgebnis:
    """Führt den vollständigen Standardprozess in definierter Reihenfolge aus."""
    ergebnis = WorkflowErgebnis()

    installation = _schritt_installation(progress)
    ergebnis.schritte.append(installation)

    analyse = _schritt_analyse(ziele, lauf_id, progress)
    ergebnis.schritte.append(analyse)
    analyse_ergebnisse = analyse.details.get("analyse_ergebnisse", [])

    ordner = _schritt_ordner_und_freigaben(basis_pfad, progress)
    ergebnis.schritte.append(ordner)

    dokumentation = _schritt_dokumentation(
        analyse_ergebnisse=analyse_ergebnisse if isinstance(analyse_ergebnisse, list) else [],
        report_pfad=report_pfad,
        logs_verzeichnis=logs_verzeichnis,
        docs_verzeichnis=docs_verzeichnis,
        progress=progress,
    )
    ergebnis.schritte.append(dokumentation)
    return ergebnis
