"""Optionale Policies für SystemAG-nahe Ordner- und Freigabekonventionen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SharePolicy:
    """Konfiguriert optionale Zusatzpfade für kompatible Zielstrukturen."""

    erstelle_systemag_kopie: bool = False
    erstelle_doku_unterordner: bool = False


def ermittle_optionale_ordner(basis_pfad: str, policy: SharePolicy | None) -> list[Path]:
    """Liefert optionale Ordner aus der Policy (z. B. ``_Kopie`` oder Doku-Unterordner)."""
    if policy is None:
        return []

    basis = Path(basis_pfad)
    ordner: list[Path] = []

    if policy.erstelle_systemag_kopie:
        ordner.append(basis.with_name(f"{basis.name}_Kopie"))

    if policy.erstelle_doku_unterordner:
        ordner.extend(
            [
                basis / "Dokumentation" / "Analysen",
                basis / "Dokumentation" / "Aenderungen",
            ]
        )

    return ordner
