import os
import sys
import logging
from tkinter import Tk, Label, filedialog

# Konfiguration fürs Logging
logging.basicConfig(
    filename=os.path.join(os.getcwd(), "logs/server_analysis_log.txt"),
    level=logging.DEBUG,
    format='[%(asctime)s] %(message)s',
)

def choose_installation_path():
    root = Tk()
    root.withdraw()  # Verstecke Hauptrahmen
    installation_dir = filedialog.askdirectory(title="Installationsverzeichnis wählen")
    return installation_dir if installation_dir else os.getcwd()

def check_installation(installation_dir):
    install_file_path = os.path.join(installation_dir, "install_complete.txt")
    logging.info(f"Prüfe den Pfad zur Installationsdatei: {install_file_path}")
    if os.path.exists(install_file_path):
        logging.info(f"Installationsdatei gefunden: {install_file_path}")
        return True
    logging.error("Installationsdatei nicht gefunden. Serveranalyse abgebrochen.")
    return False

def server_analysis(installation_dir):
    if not check_installation(installation_dir):
        sys.exit("Fehler: Installationsprüfung fehlgeschlagen.")

    logging.info("Serveranalyse begonnen...")
    # Simulation weiterer Analyse-Schritte
    try:
        logging.info("Prüfe Systemressourcen...")
        # Beispielausgabe
        memory_ok = True
        cpu_ok = True

        if not (memory_ok and cpu_ok):
            logging.error("Systemanalyse fehlgeschlagen: Nicht genügend Ressourcen.")
            sys.exit("Systemressourcen unzureichend.")

        logging.info("Systemressourcen okay.")

    except Exception as e:
        logging.error(f"Fehler während der Serveranalyse: {str(e)}")
        sys.exit(f"Serveranalyse abgebrochen: {str(e)}")

    logging.info("Serveranalyse erfolgreich abgeschlossen.")

def start_gui(status_text, status_color):
    root = Tk()
    root.title("Serverstatus")
    Label(root, text=status_text, font=("Arial", 16), fg=status_color).pack(pady=20)
    root.mainloop()

def main():
    logging.info("== Serveranalyse gestartet ==")
    installation_dir = choose_installation_path()
    if check_installation(installation_dir):
        server_analysis(installation_dir)
        status_text = "Analyse erfolgreich"
        status_color = "green"
    else:
        status_text = "Installation fehlt"
        status_color = "red"

    start_gui(status_text, status_color)

if __name__ == "__main__":
    main()