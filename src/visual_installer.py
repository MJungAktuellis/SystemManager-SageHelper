"""Legacy-Entry-Point für den visuellen Installer.

Hinweis: Dieser Pfad ist veraltet und delegiert auf ``scripts/install.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.py"


def visueller_installationsassistent() -> None:
    """Leitet auf den aktuellen Installationsassistenten weiter."""
    print("⚠️ Hinweis: 'src/visual_installer.py' ist veraltet.")
    print("➡️  Starte stattdessen den zentralen Installer aus scripts/install.py ...")
    subprocess.check_call([sys.executable, str(INSTALL_SCRIPT)])


if __name__ == "__main__":
    visueller_installationsassistent()
