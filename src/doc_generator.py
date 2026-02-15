"""
doc_generator.py

Modul zur Generierung automatischer Markdown-Dokumentationen basierend auf Serveranalyse und weiteren Modulen.

Funktionen enthalten:
1. Sammeln von Logs aus verschiedenen Modulen.
2. Generierung zusammengefasster Berichte im Markdown-Format.
3. Speicherung der Berichte in einem bestimmten Verzeichnis, z. B. für Microsoft Loop.
"""

from __future__ import annotations

from pathlib import Path

from systemmanager_sagehelper.logging_setup import konfiguriere_logger

logger = konfiguriere_logger(__name__, dateiname="doc_generator.log")


def lese_logs(log_verzeichnis: str, *, include_altformate: bool = True) -> str:
    """Liest konsolidierte Logs aus ``*.log`` und optional aus legacy ``*.txt``-Dateien."""
    logs_content: list[str] = []
    try:
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
    except Exception as exc:  # noqa: BLE001 - robuste Legacy-Verarbeitung.
        logger.error("Fehler beim Lesen der Logs: %s", exc)
    return "\n".join(logs_content)


def generiere_markdown_bericht(inhalt: str, output_pfad: str | Path) -> None:
    """Erstellt eine Markdown-Datei basierend auf gegebenem Inhalt."""
    try:
        Path(output_pfad).write_text(inhalt, encoding="utf-8")
        logger.info("Markdown-Bericht erfolgreich erstellt: %s", output_pfad)
    except Exception as exc:  # noqa: BLE001 - robuste Dateibehandlung.
        logger.error("Fehler beim Erstellen des Markdown-Berichts: %s", exc)


def erstelle_dokumentation(log_verzeichnis: str, output_verzeichnis: str) -> None:
    """Erstellt die zusammengefasste Markdown-Dokumentation aus vorhandenen Logs."""
    logger.info("Starte Dokumentationserstellung...")
    Path(output_verzeichnis).mkdir(parents=True, exist_ok=True)

    logs_inhalt = lese_logs(log_verzeichnis, include_altformate=True)
    markdown_datei = Path(output_verzeichnis) / "ServerDokumentation.md"

    generiere_markdown_bericht(logs_inhalt, markdown_datei)
    logger.info("Dokumentationserstellung abgeschlossen.")


if __name__ == "__main__":
    # Beispielaufruf
    log_dir = "logs"
    output_dir = "docs"
    erstelle_dokumentation(log_dir, output_dir)
