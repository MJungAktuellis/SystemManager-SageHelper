"""Legacy-Wrapper für die neue Mehrserver-GUI.

Historisch wurde dieses Modul direkt aus der Haupt-GUI gestartet. Damit bestehende
Aufrufe kompatibel bleiben, delegiert es nun an `server_analysis_gui`.
"""

from __future__ import annotations

from server_analysis_gui import main, start_gui

__all__ = ["main", "start_gui"]


if __name__ == "__main__":
    main()
