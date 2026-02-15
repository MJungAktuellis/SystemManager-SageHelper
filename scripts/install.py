"""Installationsassistent für SystemManager-SageHelper.

Der Assistent prüft die Python-Version und installiert Abhängigkeiten.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MIN_VERSION = (3, 11)


def pruefe_python_version() -> None:
    """Bricht mit verständlicher Meldung ab, falls Python zu alt ist."""
    if sys.version_info < MIN_VERSION:
        benoetigt = ".".join(map(str, MIN_VERSION))
        raise SystemExit(f"Python {benoetigt}+ wird benötigt. Aktuell: {sys.version.split()[0]}")


def installiere_anforderungen(repo_root: Path) -> None:
    """Installiert Paketanforderungen aus requirements.txt."""
    req = repo_root / "requirements.txt"
    if not req.exists():
        print("Keine requirements.txt gefunden, überspringe Paketinstallation.")
        return

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])


def main() -> None:
    """Startpunkt des Installationsassistenten."""
    print("=== Installation von SystemManager-SageHelper ===")
    pruefe_python_version()
    repo_root = Path(__file__).resolve().parent.parent
    installiere_anforderungen(repo_root)
    print("✅ Installation abgeschlossen.")
    print("Startbeispiel:")
    print("  python -m systemmanager_sagehelper scan --server localhost --rollen APP --out report.md")


if __name__ == "__main__":
    main()
