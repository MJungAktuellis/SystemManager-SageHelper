import os
import sys
from ping3 import ping
from tkinter import Tk, Label

# Logging Funktion zur Verwendung im gesamten Skript
def log(message, level="INFO"):
    log_file_path = os.path.join("logs", "server_analysis_log.txt")
    with open(log_file_path, "a") as file:
        file.write(f"[{level}] {message}\n")

# Installation prüfen
def check_installation():
    try:
        base_dir = os.path.dirname(__file__)
        install_file_path = os.path.join(base_dir, "install_complete.txt")

        log(f"Prüfe den Pfad zur Installationsdatei: {install_file_path}")

        if os.path.exists(install_file_path):
            log(f"Installationsdatei gefunden: {install_file_path}")
            return True

        log("Installationsdatei nicht gefunden. Serveranalyse abgebrochen.", level="ERROR")
        return False

    except Exception as e:
        log(f"Fehler bei der Prüfung der Installationsdatei: {str(e)}", level="ERROR")
        return False

# GUI zur Anzeige von Erfolg oder Fehler starten
def start_gui():
    root = Tk()
    root.title("Server Doku Helper")

    status = "Installation OK" if check_installation() else "Installation fehlt"
    color = "green" if status == "Installation OK" else "red"

    Label(root, text=status, font=("Arial", 16), fg=color).pack(pady=20)
    root.mainloop()

# Hauptprogramm
def main():
    log("== Serveranalyse gestartet ==")
    if not check_installation():
        sys.exit("Fehler bei der Installation. Bitte führen Sie das Installationsskript aus.")

    log("Serveranalyse abgeschlossen.")
    start_gui()

if __name__ == "__main__":
    main()