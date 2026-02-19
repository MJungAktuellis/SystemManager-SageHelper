"""Persistenzschicht für GUI-Zustände.

Dieses Modul kapselt das Laden und Speichern von GUI-Daten,
beispielsweise Serverlisten, Rollen oder zuletzt genutzte Ausgabepfade.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .logging_setup import konfiguriere_logger

logger = konfiguriere_logger(__name__, dateiname="gui_state.log")


_STANDARD_ZUSTAND: dict[str, Any] = {
    "onboarding": {
        "onboarding_abgeschlossen": False,
        "onboarding_version": "1.0.0",
        "onboarding_schema_version": 2,
        "onboarding_status": "ausstehend",
        "erststart_zeitpunkt": "",
        "letzter_abschluss_zeitpunkt": "",
        "abbruch_zeitpunkt": "",
    },
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
            "letzter_exportpfad": "",
            "letzter_exportzeitpunkt": "",
            "letzte_export_lauf_id": "",
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
            "letzter_exportpfad": "",
            "letzter_exportzeitpunkt": "",
            "letzte_export_lauf_id": "",
        },
        "folder_manager": {
            "ausgabepfade": {
                "basis_pfad": "",
                "letztes_protokoll": "",
            },
            "letzte_kerninfos": [],
            "bericht_verweise": [],
            "letztes_ergebnis": {},
            "laufhistorie": [],
        },
        "installer": {
            "installiert": False,
            "version": "",
            "zeitpunkt": "",
            "bericht_pfad": "",
        },
    }
}


def erstelle_installer_modulzustand(
    *,
    installiert: bool,
    version: str = "",
    zeitpunkt: str | None = None,
    bericht_pfad: str = "",
) -> dict[str, Any]:
    """Erzeugt ein konsistentes Persistenzobjekt für den Installer-Status.

    Das Schema ist bewusst klein und stabil, damit Launcher, CLI und GUI denselben
    Datenvertrag verwenden. `zeitpunkt` wird als ISO-8601-String persistiert,
    falls kein Wert übergeben wurde.
    """
    return {
        "installiert": bool(installiert),
        "version": version.strip(),
        "zeitpunkt": zeitpunkt or datetime.now().isoformat(timespec="seconds"),
        "bericht_pfad": bericht_pfad.strip(),
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
            onboarding = inhalt.get("onboarding")
            if isinstance(onboarding, dict):
                zustand["onboarding"].update(onboarding)

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

    def lade_onboarding_status(self) -> dict[str, Any]:
        """Lädt den Onboarding-Zustand mit vollständigem Fallback auf Standardwerte."""
        gesamtzustand = self.lade_gesamtzustand()
        onboarding_standard = deepcopy(_STANDARD_ZUSTAND["onboarding"])
        onboarding_datei = gesamtzustand.get("onboarding")
        if isinstance(onboarding_datei, dict):
            onboarding_standard.update(onboarding_datei)
        return self._migriere_onboarding_status(onboarding_standard)

    def speichere_onboarding_status(self, onboarding_status: dict[str, Any]) -> None:
        """Persistiert den Onboarding-Status im Gesamtzustand."""
        gesamtzustand = self.lade_gesamtzustand()
        combined_status = self.lade_onboarding_status()
        combined_status.update(onboarding_status)
        gesamtzustand["onboarding"] = self._migriere_onboarding_status(combined_status)
        self.speichere_gesamtzustand(gesamtzustand)

    @staticmethod
    def _migriere_onboarding_status(onboarding_status: dict[str, Any]) -> dict[str, Any]:
        """Normalisiert Legacy-Onboardingdaten auf das aktuelle, robuste Schema.

        Historisch enthielt der Persistenzzustand nur wenige Felder. Für stabile
        Erststarts und nachvollziehbare Zustandsübergänge werden fehlende Felder
        ergänzt und der Status deterministisch abgeleitet.
        """
        status = deepcopy(_STANDARD_ZUSTAND["onboarding"])
        status.update(onboarding_status)

        if status.get("onboarding_abgeschlossen"):
            status["onboarding_status"] = "abgeschlossen"
        elif status.get("abbruch_zeitpunkt"):
            status["onboarding_status"] = "abgebrochen"
        elif status.get("onboarding_status") not in {"ausstehend", "abgebrochen", "abgeschlossen"}:
            status["onboarding_status"] = "ausstehend"

        status["onboarding_schema_version"] = 2
        status["onboarding_version"] = str(status.get("onboarding_version") or _STANDARD_ZUSTAND["onboarding"]["onboarding_version"])
        return status
