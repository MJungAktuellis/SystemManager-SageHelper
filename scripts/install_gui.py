"""GUI-Einstiegspunkt mit robustem Fallback auf den CLI-Installer.

Standardmäßig wird der Tk-basierte Installationsassistent gestartet.
Falls die GUI nicht verfügbar ist (z. B. fehlendes Tkinter) oder beim
Start ein Fehler auftritt, fällt das Skript kontrolliert auf den
CLI-Installer zurück und protokolliert diesen Wechsel deutlich.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from systemmanager_sagehelper.installer import konfiguriere_logging

LOGGER = logging.getLogger(__name__)


def _safe_print(text: str) -> None:
    """Schreibt robust auf stdout, auch bei eingeschränkten Codepages."""
    ziel_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        ausgabe_text = text.encode(ziel_encoding, errors="replace").decode(ziel_encoding)
        print(ausgabe_text)
    except UnicodeEncodeError:
        ascii_fallback = text.encode("ascii", errors="replace").decode("ascii")
        print(ascii_fallback)


def starte_gui_installer() -> None:
    """Startet den GUI-Installer über das zentrale Installer-GUI-Modul."""
    from systemmanager_sagehelper.installer_gui import starte_installer_wizard

    starte_installer_wizard()


def starte_cli_fallback_non_interactive() -> None:
    """Startet den CLI-Installer als stabilen Fallback ohne Benutzereingaben."""
    import install as cli_installer

    # Bewusst non-interactive: Der Doppelklick-Pfad soll ohne weitere Eingaben robust laufen.
    sys.argv = ["install.py", "--non-interactive"]
    cli_installer.main()


def main() -> None:
    """Initialisiert Logging und startet GUI mit automatischem CLI-Fallback."""
    log_datei = konfiguriere_logging(REPO_ROOT)
    LOGGER.info("GUI-Installer-Launcher gestartet.")
    _safe_print("=== SystemManager-SageHelper: GUI-Installer ===")
    _safe_print(f"[INFO] Installationslog: {log_datei}")

    try:
        _safe_print("[INFO] Starte grafischen Installationsassistenten...")
        starte_gui_installer()
        LOGGER.info("GUI-Installer wurde ohne Startfehler ausgeführt.")
        return
    except Exception as fehler:
        LOGGER.exception("GUI-Start fehlgeschlagen. Wechsel auf CLI-Fallback.")
        _safe_print("[WARN] GUI-Installer konnte nicht gestartet werden.")
        _safe_print(f"[WARN] Ursache: {fehler}")
        _safe_print("[INFO] Fallback: CLI-Installer wird im Non-Interactive-Modus gestartet.")

    try:
        starte_cli_fallback_non_interactive()
    except SystemExit as exit_signal:
        # Das CLI-Skript signalisiert Fehler korrekt über SystemExit. Wir reichen den Code durch.
        code = int(exit_signal.code or 0)
        LOGGER.info("CLI-Fallback beendet mit Exit-Code %s.", code)
        raise
    except Exception as fehler:
        LOGGER.exception("CLI-Fallback ist fehlgeschlagen.")
        _safe_print(f"[ERROR] CLI-Fallback fehlgeschlagen: {fehler}")
        _safe_print(f"[INFO] Details im Log: {log_datei}")
        raise SystemExit(1) from fehler


if __name__ == "__main__":
    main()
