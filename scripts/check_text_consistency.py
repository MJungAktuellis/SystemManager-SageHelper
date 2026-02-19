"""Statischer Konsistenzcheck für bekannte englische UI-Schlüsselbegriffe.

Der Check ist bewusst leichtgewichtig und prüft nur definierte Dateien,
um unbeabsichtigte Sprachmischungen früh zu erkennen.
"""

from __future__ import annotations

from pathlib import Path
import sys

DATEIEN = [
    Path("README.md"),
    Path("CHANGELOG.md"),
    Path("src/systemmanager_sagehelper/texte.py"),
    Path("src/systemmanager_sagehelper/report.py"),
    Path("src/systemmanager_sagehelper/documentation.py"),
]

# Bekannte englische Begriffe, die in sichtbaren Texten vermieden werden sollen.
ENGLISCHE_UI_BEGRIFFE = {
    "Executive Summary": "Zusammenfassung",
    "Management Summary": "Zusammenfassung",
    "Issues": "Befunde oder offene Punkte",
    "Findings": "Befunde",
    "Actions": "Maßnahmen",
    "Artifacts": "Artefakte",
    "Done": "Erledigt oder erfolgreich",
    "Error": "Fehler",
    "Warning": "Warnung",
    "Info": "Hinweis",
}


def main() -> int:
    """Führt den Konsistenzcheck aus und liefert einen aussagekräftigen Exit-Code."""
    treffer: list[str] = []

    for datei in DATEIEN:
        inhalt = datei.read_text(encoding="utf-8")
        for englisch, empfehlung in ENGLISCHE_UI_BEGRIFFE.items():
            if englisch in inhalt:
                treffer.append(f"{datei}: '{englisch}' gefunden → Empfehlung: '{empfehlung}'")

    if treffer:
        print("Textkonsistenzprüfung fehlgeschlagen. Gefundene Begriffe:")
        for eintrag in treffer:
            print(f"- {eintrag}")
        return 1

    print("Textkonsistenzprüfung erfolgreich: Keine unerwünschten englischen UI-Schlüsselbegriffe gefunden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
