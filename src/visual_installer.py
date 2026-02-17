"""Veralteter Legacy-Entry-Point für den visuellen Installer.

DEPRECATED: Dieser Pfad bleibt nur für die Übergangsphase erhalten und
wird mittelfristig entfernt. Kanonischer Einstieg ist:
``scripts/install_assistant.ps1 -> scripts/install.py -> systemmanager_sagehelper.installer``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.py"


def visueller_installationsassistent() -> None:
    """Leitet auf den zentralen Installer um und kennzeichnet den Legacy-Status."""
    print("[WARN] DEPRECATED: 'src/visual_installer.py' wird mittelfristig entfernt.")
    print("[INFO] Starte stattdessen die kanonische Orchestrierung über scripts/install.py.")
    subprocess.check_call([sys.executable, str(INSTALL_SCRIPT), "--mode", "auto"])


if __name__ == "__main__":
    visueller_installationsassistent()
