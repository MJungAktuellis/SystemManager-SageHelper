"""Geführter Installationsassistent für SystemManager-SageHelper.

Der Assistent kann auf Windows zusätzlich Git und Python automatisch
nachinstallieren und richtet anschließend die Python-Abhängigkeiten ein.
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
    MINDEST_PYTHON_VERSION,
    InstallationsFehler,
    erzeuge_installationsbericht,
    installiere_git_unter_windows,
    installiere_python_pakete,
    installiere_python_unter_windows,
    ist_windows_system,
    konfiguriere_logging,
)

LOGGER = logging.getLogger(__name__)


def drucke_statusbericht() -> None:
    """Zeigt den aktuellen Installationsstatus in kompakter Form an."""
    print("\nSystemprüfung:")
    for status in erzeuge_installationsbericht():
        symbol = "✅" if status.gefunden else "❌"
        version = f" ({status.version})" if status.version else ""
        print(f"  {symbol} {status.name}{version}")


def validiere_python_version() -> None:
    """Bricht auf Nicht-Windows-Systemen bei zu alter Python-Version sauber ab."""
    if sys.version_info >= MINDEST_PYTHON_VERSION:
        return

    benoetigt = ".".join(map(str, MINDEST_PYTHON_VERSION))
    raise InstallationsFehler(
        f"Python {benoetigt}+ wird benötigt. Aktuell aktiv: {sys.version.split()[0]}"
    )


def fuehre_windows_bootstrap_aus() -> None:
    """Installiert fehlende Windows-Voraussetzungen, sofern möglich, automatisiert."""
    git_installiert = installiere_git_unter_windows()
    if git_installiert:
        print("✅ Git wurde installiert.")

    python_installiert = installiere_python_unter_windows()
    if python_installiert:
        print("✅ Python wurde installiert. Starte den Installer danach erneut.")
        raise SystemExit(0)


def main() -> None:
    """Startpunkt des geführten Installationsprozesses."""
    print("=== Installation von SystemManager-SageHelper ===")
    log_datei = konfiguriere_logging(REPO_ROOT)
    print(f"📄 Installationslog: {log_datei}")
    LOGGER.info("Installationslauf gestartet.")

    try:
        drucke_statusbericht()

        if ist_windows_system():
            print("\nWindows erkannt: Voraussetzungen werden bei Bedarf nachinstalliert.")
            fuehre_windows_bootstrap_aus()
        else:
            validiere_python_version()

        installiere_python_pakete(REPO_ROOT)
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
    print("Startbeispiel:")
    print("  python -m systemmanager_sagehelper scan --server localhost --rollen APP --out report.md")


if __name__ == "__main__":
    main()
