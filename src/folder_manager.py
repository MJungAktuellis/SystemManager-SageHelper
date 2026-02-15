"""
folder_manager.py

Modul zur Verwaltung und Überprüfung von Ordnerstrukturen auf Servern.

Funktionen enthalten:
1. Erstellung einer vordefinierten Ordnerstruktur.
2. Überprüfung, ob die Struktur existiert, andernfalls Ergänzung.
3. Automatische Setzung von Freigabeberechtigungen.
4. Logging zur Nachvollziehbarkeit aller Änderungen.
"""

import os
from pathlib import Path
import subprocess
import logging

# Logging-Konfiguration
logging.basicConfig(
    filename="logs/folder_manager.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def erstelle_ordnerstruktur(basis_pfad: str):
    """
    Erstellt die Ordnerstruktur unterhalb des Basis-Pfades.

    Args:
        basis_pfad (str): Hauptpfad, in dem die Struktur erstellt werden soll.
    """
    struktur = [
        "AddinsOL/abf",
        "AddinsOL/rewe",
        "Installation/Anpassungen",
        "Installation/AppDesigner",
        "Installation/CD_Ablage",
        "Installation/Lizenzen",
        "Installation/Programmierung",
        "Installation/Update",
        "LiveupdateOL",
        "Dokumentation",
        "Dokumentation/Kundenstammblatt",
        "Dokumentation/Logs"
    ]

    for rel_path in struktur:
        try:
            ziel_pfad = Path(basis_pfad) / rel_path
            ziel_pfad.mkdir(parents=True, exist_ok=True)
            logging.info(f"Ordner erstellt oder vorhanden: {ziel_pfad}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen von {ziel_pfad}: {e}")


def setze_freigaben(basis_pfad: str):
    """
    Setzt Freigaben für spezifische Ordner innerhalb der Ordnerstruktur.

    Args:
        basis_pfad (str): Hauptpfad der Ordnerstruktur.
    """
    freigaben = [
        {"ordner": basis_pfad,               "name": "SystemAG$",     "rechte": "READ"},
        {"ordner": f"{basis_pfad}/AddinsOL", "name": "AddinsOL$",     "rechte": "CHANGE"},
        {"ordner": f"{basis_pfad}/LiveupdateOL", "name": "LiveupdateOL$", "rechte": "CHANGE"}
    ]

    for freigabe in freigaben:
        try:
            # Vorherige Freigabe löschen (wenn vorhanden)
            subprocess.run(["net", "share", freigabe["name"], "/DELETE"], check=False)

            # Neue Freigabe setzen
            subprocess.run([
                "net", "share",
                f"{freigabe['name']}={freigabe['ordner']}",
                f"/GRANT:Jeder,{freigabe['rechte']}",
                "/REMARK:Automatisch erstellt"
            ], check=True)
            logging.info(f"Freigabe gesetzt: {freigabe['name']} -> {freigabe['rechte']}")
        except Exception as e:
            logging.error(f"Fehler beim Setzen der Freigabe {freigabe['name']}: {e}")


def pruefe_und_erstelle_struktur(basis_pfad: str):
    """
    Prüft, ob die Basisstruktur vorhanden ist, und erstellt sie bei Bedarf.

    Args:
        basis_pfad (str): Der Hauptpfad, an dem die Ordnerstruktur erstellt wird.
    """
    if not Path(basis_pfad).exists():
        logging.info(f"Basisstruktur nicht vorhanden, wird erstellt: {basis_pfad}")
        erstelle_ordnerstruktur(basis_pfad)
    else:
        logging.info(f"Basisstruktur ist bereits vorhanden: {basis_pfad}")
    
    # Freigaben setzen
    setze_freigaben(basis_pfad)

if __name__ == "__main__":
    # Beispielaufruf für Tests
    standard_path = "C:/SystemAG"
    pruefe_und_erstelle_struktur(standard_path)