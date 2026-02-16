"""Geführter Installationsassistent für SystemManager-SageHelper.

Dieses Skript bietet einen interaktiven Auswahlmodus für Installationskomponenten
und führt die Installation in einer festen, validierten Reihenfolge aus.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from systemmanager_sagehelper.installer import (
    InstallationsFehler,
    STANDARD_REIHENFOLGE,
    erstelle_standard_komponenten,
    erzeuge_installationsbericht,
    fuehre_installationsplan_aus,
    konfiguriere_logging,
    schreibe_installationsreport,
    validiere_auswahl_und_abhaengigkeiten,
)

LOGGER = logging.getLogger(__name__)


def drucke_statusbericht() -> None:
    """Zeigt den aktuellen Installationsstatus in kompakter Form an."""
    print("\nSystemprüfung:")
    for status in erzeuge_installationsbericht():
        symbol = "✅" if status.gefunden else "❌"
        version = f" ({status.version})" if status.version else ""
        print(f"  {symbol} {status.name}{version}")


def _frage_ja_nein(prompt: str, standard: bool = True) -> bool:
    """Fragt eine Ja/Nein-Entscheidung mit sinnvoller Standardauswahl ab."""
    suffix = "[J/n]" if standard else "[j/N]"
    eingabe = input(f"{prompt} {suffix}: ").strip().lower()

    if not eingabe:
        return standard
    if eingabe in {"j", "ja", "y", "yes"}:
        return True
    if eingabe in {"n", "nein", "no"}:
        return False

    print("⚠️ Ungültige Eingabe, Standardwert wird übernommen.")
    return standard


def ermittle_interaktive_auswahl(komponenten: dict) -> dict[str, bool]:
    """Ermittelt die gewünschte Komponentenauswahl interaktiv am Terminal."""
    print("\nInteraktiver Modus: Komponenten können optional deaktiviert werden.")
    print("Standardmäßig sind alle Komponenten aktiviert.\n")

    auswahl = {komponenten_id: komponenten[komponenten_id].default_aktiv for komponenten_id in STANDARD_REIHENFOLGE}

    for komponenten_id in STANDARD_REIHENFOLGE:
        komponente = komponenten[komponenten_id]
        aktiv = _frage_ja_nein(f"Komponente aktivieren: {komponente.name}", standard=komponente.default_aktiv)
        auswahl[komponenten_id] = aktiv

    validiere_auswahl_und_abhaengigkeiten(komponenten, auswahl)
    return auswahl


def main() -> None:
    """Startpunkt des geführten Installationsprozesses."""
    print("=== Installation von SystemManager-SageHelper ===")
    log_datei = konfiguriere_logging(REPO_ROOT)
    print(f"📄 Installationslog: {log_datei}")
    LOGGER.info("Installationslauf gestartet.")

    komponenten = erstelle_standard_komponenten(REPO_ROOT)

    try:
        drucke_statusbericht()
        auswahl = ermittle_interaktive_auswahl(komponenten)
        ergebnisse = fuehre_installationsplan_aus(komponenten, auswahl)
        report_datei = schreibe_installationsreport(REPO_ROOT, ergebnisse, auswahl)
    except InstallationsFehler as fehler:
        LOGGER.error("Installationsfehler: %s", fehler)
        print(f"❌ {fehler}")
        print(f"📄 Details im Log: {log_datei}")
        raise SystemExit(1) from fehler
    except Exception:
        LOGGER.exception("Unerwarteter Fehler während der Installation.")
        print("❌ Unerwarteter Fehler während der Installation.")
        print(f"📄 Details im Log: {log_datei}")
        raise SystemExit(1)

    LOGGER.info("Installationslauf erfolgreich abgeschlossen.")
    print("\n✅ Installation abgeschlossen.")
    print("📄 Logdatei:", log_datei)
    print("🧾 Installationsreport:", report_datei)
    print("Startbeispiel:")
    print("  python -m systemmanager_sagehelper scan --server localhost --rollen APP --out report.md")


if __name__ == "__main__":
    main()
