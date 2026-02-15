import concurrent.futures
import subprocess
import os
import sys
from ping3 import ping
from tkinter import Tk, Label, Button, Entry, Checkbutton, BooleanVar, StringVar, Frame

# Check Installation
required_modules = ["ping3"]
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        print(f"Fehlendes Modul: {module}. Bitte Modul über Installationsskript installieren.")
        sys.exit(1)

# Logging Setup
def log(message, level="INFO"):
    with open("server_analysis_log.txt", "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

log("SystemManager-SageHelper gestartet.")

# Funktion für Netzwerkscan mit `ping3`
def is_host_reachable(host):
    try:
        response = ping(host, timeout=1)
        return response is not None
    except Exception as e:
        log(f"Ping-Fehler bei {host}: {str(e)}", level="ERROR")
        return False

# Weiterer Code, z. B. Rollenprüfungs-Logik...

def start_gui():
    app = Tk()
    app.title("Server Doku Helper - Python")

    # Header
    Label(app, text="Server-Rollen Auswahl & erweiterter Netzwerkscan", font=("Arial", 16)).grid(row=0, columnspan=2, pady=10)

    # Progress label
    progress_label = Label(app, text="Bereit", fg="green")
    progress_label.grid(row=2, pady=10)

    app.mainloop()

# Main
if __name__ == "__main__":
    log("Installation wird vor Start der Serveranalyse geprüft.")
    if not os.path.exists("~\SystemManager-SageHelper\install_complete.txt"):
        sys.exit("Die Installation wurde bislang nicht abgeschlossen. Bitte führen Sie das Installationsskript aus.")
    start_gui()
