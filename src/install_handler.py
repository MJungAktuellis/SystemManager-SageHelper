"""Veralteter Legacy-Wrapper für den Installationshandler.

DEPRECATED: Dieser Pfad bleibt nur temporär aus Kompatibilitätsgründen bestehen
und wird mittelfristig entfernt. Kanonischer Einstieg ist:
``scripts/install_assistant.ps1 -> scripts/install.py -> systemmanager_sagehelper.installer``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.py"


def verarbeite_installation() -> None:
    """Delegiert auf den zentralen Installationsflow und markiert Legacy-Nutzung."""
    print("[WARN] DEPRECATED: 'src/install_handler.py' wird mittelfristig entfernt.")
    print("[INFO] Verwende den zentralen Installer unter scripts/install_assistant.ps1 oder scripts/install.py.")
    subprocess.check_call([sys.executable, str(INSTALL_SCRIPT), "--mode", "auto"])


if __name__ == "__main__":
    verarbeite_installation()
