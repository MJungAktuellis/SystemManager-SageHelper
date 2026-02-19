"""Prüfung und Planung der gewünschten SystemAG-Ordnerstruktur."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .config import STANDARD_ORDNER


@dataclass(frozen=True)
class StrukturKandidat:
    """Beschreibt einen gefundenen ``SystemAG``-Kandidaten auf lokalen Laufwerken."""

    pfad: Path
    fehlende_unterordner: list[Path]

    @property
    def ist_vollstaendig(self) -> bool:
        """Kennzeichnet, ob der Kandidat bereits alle Standardunterordner besitzt."""
        return not self.fehlende_unterordner


def ermittle_fehlende_ordner(basis_pfad: Path) -> list[Path]:
    """Liefert alle fehlenden Zielordner relativ zur gewünschten SystemAG-Struktur."""
    fehlend: list[Path] = []
    for rel_pfad in STANDARD_ORDNER:
        ziel = basis_pfad / rel_pfad
        if not ziel.exists():
            fehlend.append(ziel)
    return fehlend


def finde_systemag_kandidaten(max_tiefe: int = 3) -> list[Path]:
    """Sucht typische ``*/SystemAG``-Pfade auf lokalen Laufwerken.

    Die Suche bleibt absichtlich auf wenige Ebenen begrenzt, um auch auf großen
    Systemen performant zu bleiben.
    """
    wurzeln: list[Path] = []
    if os.name == "nt":
        for laufwerk in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            wurzel = Path(f"{laufwerk}:/")
            if wurzel.exists():
                wurzeln.append(wurzel)
    else:
        # Fallback für Nicht-Windows-Umgebungen (Tests/CI): lokale Home-Struktur.
        wurzeln.append(Path.home())

    gefundene: set[Path] = set()
    for wurzel in wurzeln:
        for tiefe in range(max_tiefe + 1):
            muster = "/".join(["*"] * tiefe + ["SystemAG"])
            for kandidat in wurzel.glob(muster):
                if kandidat.is_dir():
                    gefundene.add(kandidat)

    return sorted(gefundene)


def pruefe_systemag_kandidaten(kandidaten: list[Path]) -> list[StrukturKandidat]:
    """Bewertet gefundene Kandidaten und ergänzt fehlende Unterordner je Pfad."""
    return [StrukturKandidat(pfad=pfad, fehlende_unterordner=ermittle_fehlende_ordner(pfad)) for pfad in kandidaten]


def lege_ordner_an(pfade: list[Path]) -> None:
    """Legt fehlende Ordner robust an (inkl. Elternverzeichnisse)."""
    for pfad in pfade:
        pfad.mkdir(parents=True, exist_ok=True)
