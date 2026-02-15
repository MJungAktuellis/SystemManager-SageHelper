"""
install_assistant.py

Automatische Einrichtung und Konfiguration des SystemManager-SageHelper.
Funktionen enthalten:
1. Überprüfung der Python-Installation.
2. Installation von Abhängigkeiten.
3. Erstellung der notwendigen Verzeichnisse.
4. Kurzer Test aller Module nach der Installation.
"""

import subprocess
import sys
import os
from pathlib import Path

def python_version_pruefen():
    """
    Prüft, ob Python in der richtigen Version installiert ist.
    """
    print("\n=== Überprüfung der Python-Version ===")
    if sys.version_info < (3, 11):
        print("Python 3.11 oder höher ist erforderlich. Bitte aktualisieren.")
        sys.exit(1)
    print("✓ Python-Version ist kompatibel: ", sys.version)

def abhaengigkeiten_installieren():
    """
    Installiert Packages aus der requirements.txt.
    """
    print("\n=== Installation von Abhängigkeiten ===")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Alle Abhängigkeiten erfolgreich installiert.")
    except Exception as e:
        print("Fehler bei der Installation von Abhängigkeiten:", e)
        sys.exit(1)

def initiale_verzeichnisse_erstellen(verzeichnis_pfade: list):
    """
    Erstellt notwendige Verzeichnisse, falls diese nicht existieren.
    """
    print("\n=== Erstellung notwendiger Verzeichnisse ===")
    for pfad in verzeichnis_pfade:
        Path(pfad).mkdir(parents=True, exist_ok=True)
        print(f"✓ Verzeichnis erstellt oder vorhanden: {pfad}")

def module_testen():
    """
    Führt einfache Tests für jedes Modul aus, um Funktionalität zu verifizieren.
    """
    print("\n=== Test aller Module ===")
    try:
        subprocess.check_call([sys.executable, "src/server_analysis.py"])
        subprocess.check_call([sys.executable, "src/folder_manager.py"])
        subprocess.check_call([sys.executable, "src/doc_generator.py"])
        print("✓ Alle Module erfolgreich getestet.")
    except Exception as e:
        print("Fehler beim Testen der Module:", e)
        sys.exit(1)

def main():
    print("======== SystemManager-SageHelper Installation-Assistent ========")
    python_version_pruefen()

    # Installiere Abhängigkeiten
    abhaengigkeiten_installieren()

    # Basispfade anlegen
    initiale_verzeichnisse_erstellen([
        "logs",
        "docs",
        "output"
    ])

    # Module testen
    module_testen()

    print("\nInstallation abgeschlossen! Sie können das Programm jetzt verwenden.")
    print("Starten Sie die Serveranalyse mit: python src/server_analysis.py")

if __name__ == "__main__":
    main()