"""Legacy-Wrapper auf ``systemmanager_sagehelper.share_manager``.

Single Source of Truth für Ordner/Freigaben liegt im Paketmodul.
Dieses Legacy-Modul bleibt nur für bestehende Imports erhalten.
"""

from __future__ import annotations

import subprocess

from systemmanager_sagehelper.installation_state import pruefe_installationszustand, verarbeite_installations_guard
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, setze_lauf_id
from systemmanager_sagehelper.share_manager import (
    FreigabeErgebnis,
    erstelle_ordnerstruktur,
    pruefe_und_erstelle_struktur,
    setze_freigaben,
)

__all__ = [
    "FreigabeErgebnis",
    "erstelle_ordnerstruktur",
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

    setze_lauf_id(erstelle_lauf_id())
    pruefe_und_erstelle_struktur("C:/SystemAG")


if __name__ == "__main__":
    main()
