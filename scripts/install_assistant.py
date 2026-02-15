import os
import subprocess
import sys
from tkinter import Tk, filedialog, messagebox

def log(message, level="INFO"):
    log_path = "install_log.txt"
    with open(log_path, "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

def create_directory_structure(base_dir):
    try:
        os.makedirs(base_dir, exist_ok=True)
        log(f"Überordner erstellt: {base_dir}")

        subfolders = ["src", "tests", "logs", "docs"]
        for folder in subfolders:
            path = os.path.join(base_dir, folder)
            os.makedirs(path, exist_ok=True)
            log(f"Unterordner erstellt: {path}")

    except Exception as e:
        log(f"Fehler beim Erstellen der Ordnerstruktur: {str(e)}", level="ERROR")
        messagebox.showerror("Fehler", f"Ordnerstruktur konnte nicht erstellt werden: {str(e)}")
        sys.exit(1)

def check_python_version():
    if sys.version_info < (3, 7):
        raise EnvironmentError("Python 3.7 oder höher ist erforderlich.")

def install_dependencies():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ping3"])
        log("ping3 erfolgreich installiert.")
    except subprocess.CalledProcessError as e:
        log(f"Fehler bei der Installation einer Abhängigkeit: {str(e)}", level="ERROR")
        messagebox.showinfo("Fehler", "Fehler bei der Installation von Abhängigkeiten: ping3")
        sys.exit(1)

def select_installation_directory():
    root = Tk()
    root.withdraw()
    installation_dir = filedialog.askdirectory(title="Installationsverzeichnis auswählen")
    if not installation_dir:
        installation_dir = os.path.join(os.environ["ProgramFiles"], "SystemManager-SageHelper")
    log(f"Ausgewähltes Installationsverzeichnis: {installation_dir}")
    return installation_dir

def main():
    try:
        log("Starte die Installation...")
        check_python_version()
        installation_dir = select_installation_directory()
        create_directory_structure(installation_dir)
        install_dependencies()

        install_file_path = os.path.join(installation_dir, "install_complete.txt")
        with open(install_file_path, "w") as f:
            f.write("Installation abgeschlossen.")
        log(f"Installationsdatei erstellt: {install_file_path}")

        log("Installation abgeschlossen.")
        messagebox.showinfo("Erfolg", "Installation abgeschlossen. Anwendung kann gestartet werden.")
    except EnvironmentError as e:
        log(f"Fehler: {str(e)}", level="ERROR")
        messagebox.showerror("Fehler", f"Installationsfehler: {str(e)}")
    except Exception as e:
        log(f"Unbekannter Fehler: {str(e)}", level="ERROR")
        messagebox.showerror("Fehler", f"Unbekannt: {str(e)}")

if __name__ == "__main__":
    main()