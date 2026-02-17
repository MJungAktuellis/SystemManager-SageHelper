"""Legacy-Wrapper auf ``systemmanager_sagehelper``-Module.

Für bestehende Imports werden die Kernfunktionen aus ``share_manager`` exportiert.
Der direkte Einstieg startet jedoch den neuen GUI-Assistenten statt eines
harten Legacy-Aufrufs mit festem Pfad.
"""

from __future__ import annotations

from systemmanager_sagehelper.installation_state import pruefe_installationszustand, verarbeite_installations_guard
from systemmanager_sagehelper.share_manager import (
    FreigabeErgebnis,
    erstelle_ordnerstruktur,
    plane_freigabeaenderungen,
    pruefe_und_erstelle_struktur,
    setze_freigaben,
)
from systemmanager_sagehelper.folder_gui import start_gui

__all__ = [
    "FreigabeErgebnis",
    "erstelle_ordnerstruktur",
    "plane_freigabeaenderungen",
    "setze_freigaben",
    "pruefe_und_erstelle_struktur",
]


def main() -> None:
    """Direkter Einstieg mit Installationsschutz."""

    def _zeige_fehler(text: str) -> None:
        print(f"❌ {text}")

    def _frage_installation(_frage: str) -> bool:
        antwort = input("Installation starten? [j/N]: ").strip().lower()
        return antwort in {"j", "ja", "y", "yes"}

    freigegeben = verarbeite_installations_guard(
        pruefe_installationszustand(),
        modulname="Ordnerverwaltung",
        fehlermeldung_fn=_zeige_fehler,
        installationsfrage_fn=_frage_installation,
    )
    if not freigegeben:
        return

    start_gui()


if __name__ == "__main__":
    main()
