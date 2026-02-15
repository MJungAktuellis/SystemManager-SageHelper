"""Prüfung und Planung der gewünschten SystemAG-Ordnerstruktur."""

from __future__ import annotations

from pathlib import Path

from .config import STANDARD_ORDNER


def ermittle_fehlende_ordner(basis_pfad: Path) -> list[Path]:
    """Liefert alle fehlenden Zielordner relativ zur gewünschten SystemAG-Struktur."""
    fehlend: list[Path] = []
    for rel_pfad in STANDARD_ORDNER:
        ziel = basis_pfad / rel_pfad
        if not ziel.exists():
            fehlend.append(ziel)
    return fehlend


def lege_ordner_an(pfade: list[Path]) -> None:
    """Legt fehlende Ordner robust an (inkl. Elternverzeichnisse)."""
    for pfad in pfade:
        pfad.mkdir(parents=True, exist_ok=True)
