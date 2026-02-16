"""Legacy-Wrapper für den alten Installationshandler.

Hinweis: Dieser Pfad bleibt aus Kompatibilitätsgründen bestehen und delegiert
auf ``scripts/install.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.py"


def verarbeite_installation() -> None:
    """Leitet den Aufruf auf den neuen Installationsworkflow um."""
    print("⚠️ Hinweis: 'src/install_handler.py' ist veraltet.")
    print("➡️  Verwende den zentralen Installer unter scripts/install.py.")
    subprocess.check_call([sys.executable, str(INSTALL_SCRIPT)])


if __name__ == "__main__":
    verarbeite_installation()
