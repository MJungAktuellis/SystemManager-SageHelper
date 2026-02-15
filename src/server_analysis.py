"""Einfache Tkinter-Oberfläche für eine manuell gestartete Serveranalyse.

Dieses Modul dient als Legacy-Einstieg aus der GUI (`src/gui_manager.py`) und nutzt
intern die moderne Analyse-Logik aus `systemmanager_sagehelper.analyzer`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter import Button, Entry, Label, Tk

from systemmanager_sagehelper.analyzer import analysiere_server
from systemmanager_sagehelper.models import ServerZiel


def _konfiguriere_logging() -> None:
    """Initialisiert Datei-Logging mit robustem Pfad-Handling."""
    log_verzeichnis = Path.cwd() / "logs"
    log_verzeichnis.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=log_verzeichnis / "server_analysis_log.txt",
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
    )


def _starte_analyse(servername: str, rollen_text: str) -> str:
    """Führt eine echte Analyse aus und liefert eine kurze Statusmeldung für die GUI."""
    rollen = [rolle.strip().upper() for rolle in rollen_text.split(",") if rolle.strip()]
    ergebnis = analysiere_server(ServerZiel(name=servername.strip(), rollen=rollen))

    offene_ports = [str(p.port) for p in ergebnis.ports if p.offen]
    status = "Keine relevanten Ports offen" if not offene_ports else f"Offene Ports: {', '.join(offene_ports)}"

    logging.info("Analyse für %s abgeschlossen. %s", ergebnis.server, status)
    if ergebnis.hinweise:
        logging.info("Hinweise: %s", " | ".join(ergebnis.hinweise))

    return status


def start_gui() -> None:
    """Startet die GUI für die lokale oder remote Serveranalyse."""
    _konfiguriere_logging()

    root = Tk()
    root.title("SystemManager-SageHelper – Serveranalyse")

    Label(root, text="Server Doku Helper", font=("Arial", 20), fg="black").pack(pady=10)

    Label(root, text="Servername (z. B. localhost oder srv-app-01):").pack(pady=2)
    entry_server = Entry(root, width=40)
    entry_server.insert(0, "localhost")
    entry_server.pack(pady=2)

    Label(root, text="Rollen (kommagetrennt, z. B. APP,SQL,CTX):").pack(pady=2)
    entry_rollen = Entry(root, width=40)
    entry_rollen.insert(0, "APP")
    entry_rollen.pack(pady=2)

    label_result = Label(root, text="Warte auf Beginn der Analyse...", font=("Arial", 12), fg="blue")
    label_result.pack(pady=15)

    def run_analysis() -> None:
        servername = entry_server.get().strip()
        if not servername:
            label_result.config(text="Bitte einen Servernamen eingeben.", fg="red")
            return

        try:
            ergebnis_text = _starte_analyse(servername, entry_rollen.get())
            label_result.config(text=ergebnis_text, fg="green")
        except Exception as exc:  # noqa: BLE001 - GUI soll Fehler robust anzeigen.
            logging.exception("Fehler bei der Serveranalyse")
            label_result.config(text=f"Analyse fehlgeschlagen: {exc}", fg="red")

    Button(root, text="Serveranalyse starten", command=run_analysis, width=30, height=2).pack(pady=10)

    root.mainloop()


def main() -> None:
    """Programmstart mit Logging."""
    logging.info("=== Programm gestartet ===")
    start_gui()
    logging.info("=== Programm beendet ===")


if __name__ == "__main__":
    main()
