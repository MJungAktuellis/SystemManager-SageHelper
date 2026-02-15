import os
import zipfile
import shutil
from pathlib import Path

def entpacke_zip(quelle: str, ziel: str):
    """Entpackt eine ZIP-Datei in ein Zielverzeichnis."""
    try:
        with zipfile.ZipFile(quelle, 'r') as zip_ref:
            zip_ref.extractall(ziel)
        print(f"✅ ZIP-Datei '{quelle}' erfolgreich nach '{ziel}' entpackt.")
    except zipfile.BadZipFile:
        raise ValueError("❌ Fehler: Ungültige ZIP-Datei.")

def installiere_modul(modul_pfad: str):
    """Installiert ein Python-Modul aus einem Verzeichnis."""
    try:
        os.system(f"pip install {modul_pfad}")
        print(f"✅ Modul aus '{modul_pfad}' erfolgreich installiert.")
    except Exception as e:
        raise RuntimeError(f"❌ Fehler bei der Modulinstallation: {e}")

def bereinige_verzeichnis(verzeichnis: str):
    """Löscht ein Verzeichnis und alle Inhalte darin."""
    if os.path.exists(verzeichnis):
        shutil.rmtree(verzeichnis)
        print(f"📁 Verzeichnis '{verzeichnis}' gelöscht.")

def verarbeite_installation(zip_pfad: str, ziel_verzeichnis: str):
    """Hauptprozess: Entpacken, Installieren und Aufräumen."""
    staging_dir = Path(ziel_verzeichnis)
    staging_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Entpacken
        entpacke_zip(zip_pfad, ziel_verzeichnis)

        # Modul installieren
        installiere_modul(str(staging_dir))
    
    finally:
        # Bereinigung
        bereinige_verzeichnis(ziel_verzeichnis)

if __name__ == "__main__":
    zip_datei = "upload/modul.zip"  # Beispielpfad zur ZIP-Datei
    ziel = "staging_area"
    verarbeite_installation(zip_datei, ziel)