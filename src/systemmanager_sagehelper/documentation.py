"""Erzeugung von zusammengefassten Markdown-Dokumentationen aus Logdateien."""

from __future__ import annotations

from pathlib import Path

from .logging_setup import konfiguriere_logger

logger = konfiguriere_logger(__name__, dateiname="doc_generator.log")


def lese_logs(log_verzeichnis: str, *, include_altformate: bool = True) -> str:
    """Liest konsolidierte Logs aus ``*.log`` und optional aus Legacy-``*.txt``-Dateien."""
    logs_content: list[str] = []
    basis = Path(log_verzeichnis)
    muster = ["*.log"]
    if include_altformate:
        muster.append("*.txt")

    log_pfade: list[Path] = []
    for pattern in muster:
        log_pfade.extend(sorted(basis.glob(pattern)))

    for log_pfad in log_pfade:
        inhalt = log_pfad.read_text(encoding="utf-8")
        logs_content.append(f"# Log-Datei: {log_pfad.name}\n")
        logs_content.append(inhalt + "\n")

    logger.info("Alle Logs erfolgreich gelesen. Dateien: %s", [pfad.name for pfad in log_pfade])
    return "\n".join(logs_content)


def generiere_markdown_bericht(inhalt: str, output_pfad: str | Path) -> None:
    """Erstellt eine Markdown-Datei basierend auf gegebenem Inhalt."""
    Path(output_pfad).write_text(inhalt, encoding="utf-8")
    logger.info("Markdown-Bericht erfolgreich erstellt: %s", output_pfad)


def erstelle_dokumentation(log_verzeichnis: str, output_verzeichnis: str) -> Path:
    """Erstellt die zusammengefasste Markdown-Dokumentation aus vorhandenen Logs."""
    logger.info("Starte Dokumentationserstellung...")
    ziel = Path(output_verzeichnis)
    ziel.mkdir(parents=True, exist_ok=True)

    logs_inhalt = lese_logs(log_verzeichnis, include_altformate=True)
    markdown_datei = ziel / "ServerDokumentation.md"
    generiere_markdown_bericht(logs_inhalt, markdown_datei)
    logger.info("Dokumentationserstellung abgeschlossen.")
    return markdown_datei
