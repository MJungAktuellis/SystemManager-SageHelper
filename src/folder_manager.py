"""Legacy-Wrapper auf ``systemmanager_sagehelper.share_manager``.

Single Source of Truth für Ordner/Freigaben liegt im Paketmodul.
Dieses Legacy-Modul bleibt nur für bestehende Imports erhalten.
"""

from __future__ import annotations

import subprocess

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


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    pruefe_und_erstelle_struktur("C:/SystemAG")
