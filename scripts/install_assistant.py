"""Veralteter Legacy-Einstieg für den Installationsassistenten.

DEPRECATED: Dieser Einstieg bleibt nur für eine Übergangsphase bestehen und
leitet auf den kanonischen Flow um:
``scripts/install_assistant.ps1 -> scripts/install.py -> systemmanager_sagehelper.installer``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.py"


def main() -> None:
    """Delegiert auf die kanonische Python-Orchestrierung und markiert den Legacy-Pfad."""
    print("[WARN] DEPRECATED: 'scripts/install_assistant.py' wird mittelfristig entfernt.")
    print("[INFO] Verwende stattdessen 'scripts/install_assistant.ps1' oder 'scripts/install.py'.")
    subprocess.check_call([sys.executable, str(INSTALL_SCRIPT), "--mode", "auto"])


if __name__ == "__main__":
    main()
