"""Legacy-Wrapper für die neue Mehrserver-GUI.

Historisch wurde dieses Modul direkt aus der Haupt-GUI gestartet. Damit bestehende
Aufrufe kompatibel bleiben, delegiert es nun an `server_analysis_gui`.
"""

from __future__ import annotations

from server_analysis_gui import main, start_gui
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id

logger = konfiguriere_logger(__name__, dateiname="server_analysis.log")

__all__ = ["main", "start_gui"]


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    logger.info("Legacy-Einstieg src/server_analysis.py wurde gestartet")
    main()
