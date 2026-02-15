"""
doc_generator.py

Modul zur Generierung automatischer Markdown-Dokumentationen basierend auf Serveranalyse und weiteren Modulen.

Funktionen enthalten:
1. Sammeln von Logs aus verschiedenen Modulen.
2. Generierung zusammengefasster Berichte im Markdown-Format.
3. Speicherung der Berichte in einem bestimmten Verzeichnis, z. B. für Microsoft Loop.
"""

from pathlib import Path
import logging

# Logging-Konfiguration
logging.basicConfig(
    filename="logs/doc_generator.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def lese_logs(log_verzeichnis: str) -> str:
    """
    Liest alle Log-Dateien in einem Verzeichnis und gibt diese als zusammengefassten String zurück.

    Args:
        log_verzeichnis (str): Pfad zum Verzeichnis mit Log-Dateien.

    Returns:
        str: Konsolidierter Inhalt der Log-Dateien.
    """
    logs_content = []
    try:
        log_pfade = Path(log_verzeichnis).glob("*.log")
        for log_pfad in log_pfade:
            with open(log_pfad, "r", encoding="utf-8") as f:
                logs_content.append(f"# Log-Datei: {log_pfad.name}\n")
                logs_content.append(f.read() + "\n")
        logging.info("Alle Logs erfolgreich gelesen.")
    except Exception as e:
        logging.error(f"Fehler beim Lesen der Logs: {e}")
    return "\n".join(logs_content)

def generiere_markdown_bericht(inhalt: str, output_pfad: str):
    """
    Erstellt eine Markdown-Datei basierend auf gegebenem Inhalt.

    Args:
        inhalt (str): Inhalt, der in die Markdown-Datei geschrieben wird.
        output_pfad (str): Pfad und Name der Markdown-Ausgabedatei.
    """
    try:
        with open(output_pfad, "w", encoding="utf-8") as f:
            f.write(inhalt)
        logging.info(f"Markdown-Bericht erfolgreich erstellt: {output_pfad}")
    except Exception as e:
        logging.error(f"Fehler beim Erstellen des Markdown-Berichts: {e}")

def erstelle_dokumentation(log_verzeichnis: str, output_verzeichnis: str):
    """
    Hauptprozess zur Erstellung einer zusammengefassten Markdown-Dokumentation aus Log-Dateien.

    Args:
        log_verzeichnis (str): Verzeichnis, in dem die Logs gespeichert sind.
        output_verzeichnis (str): Zielverzeichnis für die Markdown-Dokumentation.
    """
    logging.info("Starte Dokumentationserstellung...")
    Path(output_verzeichnis).mkdir(parents=True, exist_ok=True)

    logs_inhalt = lese_logs(log_verzeichnis)
    markdown_datei = Path(output_verzeichnis) / "ServerDokumentation.md"

    generiere_markdown_bericht(logs_inhalt, markdown_datei)
    logging.info("Dokumentationserstellung abgeschlossen.")

if __name__ == "__main__":
    # Beispielaufruf
    log_dir = "logs"
    output_dir = "docs"
    erstelle_dokumentation(log_dir, output_dir)