import concurrent.futures
import subprocess
import os
import sys
from ping3 import ping
from tkinter import Tk, Label, Button, Entry, Checkbutton, BooleanVar, StringVar, Frame

# Zusätzliche Fehlerbehebung und Logging
log_file_path = "server_analysis_log.txt"

def log(message, level="INFO"):
    with open(log_file_path, "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

log("== Serveranalyse gestartet ==")

# Prüfung auf installierte Module vor Serveranalyse
required_modules = ["ping3"]
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        log(f"Fehlendes Modul: {module}. Bitte installieren.", level="ERROR")
        sys.exit(1)

log("Alle Module erfolgreich geprüft.")

# Funktion: Host-Erreichbarkeit prüfen
def is_host_reachable(host):
    try:
        response = ping(host, timeout=2)
        if response is not None:
            log(f"Host {host} erreichbar. Antwortzeit: {response:.2f} ms")
            return True
        log(f"Host {host} nicht erreichbar. Keine Antwort.")
        return False

    except Exception as e:
        log(f"Fehler bei Ping {host}: {str(e)}", level="ERROR")
        return False

# GUI für die Serveranalyse starten
def start_gui():
    app = Tk()
    app.title("Server Doku Helper - Python")
    Label(app, text="Server-Rollen Auswahl & Netzwerkscan", font=("Arial", 16)).grid(row=0, columnspan=2, pady=10)
    progress_label = Label(app, text="Bereit", fg="green")
    progress_label.grid(row=2, pady=10)
    app.mainloop()

# Main
if __name__ == "__main__":
    log("Installation wird vor Serveranalyse geprüft.")
    installation_file = os.path.join(os.path.expanduser("~"), "SystemManager-SageHelper", "install_complete.txt")

    if not os.path.exists(installation_file):
        log("Installationsdatei nicht gefunden. Serveranalyse abgebrochen.", level="ERROR")
        sys.exit("Die Installation wurde nicht abgeschlossen. Bitte führen Sie das Installationsskript aus.")

    log("Serveranalyse gestartet.")
    start_gui()