"""Persistenzschicht für GUI-Zustände.

Dieses Modul kapselt das Laden und Speichern von GUI-Daten,
beispielsweise Serverlisten, Rollen oder zuletzt genutzte Ausgabepfade.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .logging_setup import konfiguriere_logger

logger = konfiguriere_logger(__name__, dateiname="gui_state.log")


_STANDARD_ZUSTAND: dict[str, Any] = {
    "modules": {
        "gui_manager": {
            "serverlisten": [],
            "rollen": {},
            "letzte_discovery_range": "",
            "ausgabepfade": {
                "analyse_report": "docs/serverbericht.md",
                "log_report": "logs/log_dokumentation.md",
            },
            "letzte_kerninfos": [],
            "bericht_verweise": [],
        },
        "server_analysis": {
            "serverlisten": [],
            "rollen": {},
            "letzte_discovery_range": "",
            "ausgabepfade": {
                "analyse_report": "docs/serverbericht.md",
                "log_report": "logs/log_dokumentation.md",
            },
            "letzte_kerninfos": [],
            "bericht_verweise": [],
        },
    }
}


class GUIStateStore:
    """Verwaltet den persistenten Zustand der GUI als JSON-Datei."""

    def __init__(self, dateipfad: Path | None = None) -> None:
        projektwurzel = Path(__file__).resolve().parents[2]
        self.dateipfad = dateipfad or projektwurzel / "config" / "gui_state.json"

    def lade_gesamtzustand(self) -> dict[str, Any]:
        """Lädt den gesamten Zustand robust mit Fallback auf Standardwerte."""
        if not self.dateipfad.exists():
            return deepcopy(_STANDARD_ZUSTAND)

        try:
            inhalt = json.loads(self.dateipfad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.exception("GUI-Zustand konnte nicht gelesen werden. Standardzustand wird verwendet.")
            return deepcopy(_STANDARD_ZUSTAND)

        # Defensiv zusammenführen, damit neue Felder bei Altdateien ergänzt werden.
        zustand = deepcopy(_STANDARD_ZUSTAND)
        if isinstance(inhalt, dict):
            module = inhalt.get("modules")
            if isinstance(module, dict):
                for modulname, modulwerte in module.items():
                    if modulname not in zustand["modules"]:
                        zustand["modules"][modulname] = {}
                    if isinstance(modulwerte, dict):
                        zustand["modules"][modulname].update(modulwerte)
        return zustand

    def speichere_gesamtzustand(self, zustand: dict[str, Any]) -> None:
        """Persistiert den gesamten Zustand atomar in UTF-8."""
        self.dateipfad.parent.mkdir(parents=True, exist_ok=True)
        self.dateipfad.write_text(json.dumps(zustand, ensure_ascii=False, indent=2), encoding="utf-8")

    def lade_modulzustand(self, modulname: str) -> dict[str, Any]:
        """Liefert den Zustand eines Moduls inklusive Fallback auf Default-Struktur."""
        gesamtzustand = self.lade_gesamtzustand()
        module = gesamtzustand.setdefault("modules", {})
        default_modul = _STANDARD_ZUSTAND["modules"].get("gui_manager", {})
        modulzustand = module.setdefault(modulname, deepcopy(default_modul))
        return modulzustand

    def speichere_modulzustand(self, modulname: str, modulzustand: dict[str, Any]) -> None:
        """Speichert den Zustand eines Moduls zurück in die JSON-Datei."""
        gesamtzustand = self.lade_gesamtzustand()
        gesamtzustand.setdefault("modules", {})[modulname] = modulzustand
        self.speichere_gesamtzustand(gesamtzustand)
