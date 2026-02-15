import os
import subprocess
import sys
from tkinter import Tk, filedialog, messagebox

def log(message, level="INFO"):
    with open("install_log.txt", "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

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
        os.makedirs(installation_dir, exist_ok=True)
        install_dependencies()

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