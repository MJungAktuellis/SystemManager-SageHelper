import os
import sys
import logging
from tkinter import Tk, Label, Button

# Konfiguration fürs Logging
logging.basicConfig(
    filename=os.path.join(os.getcwd(), "logs/server_analysis_log.txt"),
    level=logging.DEBUG,
    format='[%(asctime)s] %(message)s'
)

def get_installation_path():
    """
    Sucht das Installationsverzeichnis automatisch.
    """
    installation_dir = os.path.dirname(os.path.abspath(__file__))
    return installation_dir

def check_installation(installation_dir):
    install_file_path = os.path.join(installation_dir, "install_complete.txt")
    logging.info(f"Prüfe den Pfad zur Installationsdatei: {install_file_path}")
    if os.path.exists(install_file_path):
        logging.info(f"Installationsdatei gefunden: {install_file_path}")
        return True

    logging.error("Installationsdatei nicht gefunden. Serveranalyse abgebrochen.")
    return False

def server_analysis(installation_dir):
    """
    Führt die Serveranalyse durch.
    """
    logging.info("Serveranalyse gestartet...")
    if not check_installation(installation_dir):
        logging.error("Die Installation wurde nicht abgeschlossen. Serveranalyse abgebrochen.")
        return "Fehler bei der Installation."

    # Beispiel: Führe eine simulierte Analyse durch
    try:
        logging.info("Prüfe Systemressourcen...")
        memory_ok = True  # Simulationswert
        cpu_ok = True     # Simulationswert

        if not (memory_ok and cpu_ok):
            logging.error("Systemressourcen nicht ausreichend.")
            return "Systemressourcen unzureichend."

        logging.info("Systemressourcen geprüft und erfolgreich.")

        # Weitere Schritte, die in einer Analyse auftreten sollten
        logging.info("Prüfe Serververfügbarkeit...")

        server_available = True
        if not server_available:
            logging.error("Server nicht erreichbar.")
            return "Server nicht erreichbar."

    except Exception as e:
        logging.error(f"Fehler bei der Serveranalyse: {str(e)}")
        return str(e)

    logging.info("Serveranalyse erfolgreich abgeschlossen.")
    return "Serveranalyse erfolgreich abgeschlossen."

def start_gui():
    """
    Startet die GUI für die Serververwaltung.
    """
    root = Tk()
    root.title("Server Doku Helper")

    def run_analysis():
        installation_dir = get_installation_path()
        result = server_analysis(installation_dir)
        label_result.config(text=result, fg="green" if "erfolgreich" in result else "red")

    Label(root, text="Server Doku Helper", font=("Arial", 20), fg="black").pack(pady=10)

    Button(root, text="Serveranalyse starten", command=run_analysis, width=30, height=2).pack(pady=10)

    label_result = Label(root, text="Warte auf Beginn der Analyse...", font=("Arial", 14), fg="blue")
    label_result.pack(pady=20)

    root.mainloop()

def main():
    logging.info("=== Programm gestartet ===")
    start_gui()
    logging.info("=== Programm beendet ===")

if __name__ == "__main__":
    main()