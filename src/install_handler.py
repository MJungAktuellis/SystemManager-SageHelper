import os
import zipfile
import shutil
import logging
from pathlib import Path

# Logging konfigurieren
logging.basicConfig(
    filename="install_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def entpacke_zip(quelle: str, ziel: str):
    """Entpackt eine ZIP-Datei in ein Zielverzeichnis und loggt mögliche Fehler."""
    try:
        with zipfile.ZipFile(quelle, 'r') as zip_ref:
            zip_ref.extractall(ziel)
        logging.info(f"ZIP-Datei '{quelle}' erfolgreich nach '{ziel}' entpackt.")
        print(f"✅ ZIP-Datei '{quelle}' erfolgreich nach '{ziel}' entpackt.")
    except FileNotFoundError:
        logging.error(f"Die Datei '{quelle}' wurde nicht gefunden. Bitte geben Sie einen gültigen Pfad ein.")
        raise FileNotFoundError(f"❌ Fehler: Die Datei '{quelle}' wurde nicht gefunden. Bitte prüfen Sie den Pfad.")
    except zipfile.BadZipFile:
        logging.error("Ungültige ZIP-Datei.")
        raise ValueError("❌ Fehler: Ungültige ZIP-Datei.")
    except PermissionError:
        logging.error("Zugriff verweigert beim Entpacken in das Zielverzeichnis.")
        raise PermissionError(f"❌ Fehler: Keine Berechtigung für das Zielverzeichnis: {ziel}")

def installiere_modul(modul_pfad: str):
    """Installiert ein Python-Modul aus einem Verzeichnis und loggt mögliche Fehler."""
    try:
        os.system(f"pip install {modul_pfad}")
        logging.info(f"Modul aus '{modul_pfad}' erfolgreich installiert.")
        print(f"✅ Modul aus '{modul_pfad}' erfolgreich installiert.")
    except Exception as e:
        logging.error(f"Fehler bei der Modulinstallation: {e}")
        raise RuntimeError(f"❌ Fehler bei der Modulinstallation: {e}")

def bereinige_verzeichnis(verzeichnis: str):
    """Löscht ein Verzeichnis und alle Inhalte darin."""
    if os.path.exists(verzeichnis):
        shutil.rmtree(verzeichnis)
        logging.info(f"Verzeichnis '{verzeichnis}' gelöscht.")
        print(f"📁 Verzeichnis '{verzeichnis}' gelöscht.")

def verarbeite_installation():
    """Hauptprozess: Entpacken, Installieren und Aufräumen. Logs werden erzeugt."""
    # Pfad zur ZIP-Datei abfragen
    zip_datei = input("Bitte geben Sie den Pfad zur ZIP-Datei an: ").strip()
    ziel_verzeichnis = "C:\\Program Files\\SystemManager-SageHelper"
    staging_dir = Path(ziel_verzeichnis)

    try:
        # Zielverzeichnis sicherstellen
        if not staging_dir.exists():
            staging_dir.mkdir(parents=True)
            logging.info(f"Zielverzeichnis '{ziel_verzeichnis}' erstellt.")

        # Entpacken
        entpacke_zip(zip_datei, ziel_verzeichnis)

        # Modul installieren
        installiere_modul(str(staging_dir))
    
    except FileNotFoundError as fnf_error:
        print(f"❌ Fehler: {fnf_error}")
        logging.error(fnf_error)
    except PermissionError as pe:
        print(f"❌ Berechtigungsfehler: {pe}")
        logging.error("Abbruch aufgrund fehlender Berechtigungen.")
    except Exception as e:
        print(f"❌ Fehler während der Installation: {e}")
        logging.error("Installation fehlgeschlagen.", exc_info=True)
    
    finally:
        print("Drücken Sie eine beliebige Taste, um das Programm zu beenden...")
        input()  # Warte auf Benutzereingabe, um Konsole offen zu halten

if __name__ == "__main__":
    verarbeite_installation()