"""Pytest-Konfiguration für konsistente Importpfade im Projekt."""

from __future__ import annotations

import sys
from pathlib import Path

# Stellt sicher, dass `src/` für alle Tests importierbar ist.
PROJEKT_WURZEL = Path(__file__).resolve().parents[1]
SRC_PFAD = PROJEKT_WURZEL / "src"
if str(SRC_PFAD) not in sys.path:
    sys.path.insert(0, str(SRC_PFAD))
