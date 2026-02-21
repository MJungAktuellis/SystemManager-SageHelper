"""Regressionstests für den Windows-CMD-Launcher."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CMD_PATH = REPO_ROOT / "Install-SystemManager-SageHelper.cmd"


def test_cmd_launcher_fallback_bei_powershell_fehler_ausser_spezialcodes() -> None:
    """Stellt sicher, dass generische PowerShell-Fehler den Python-Fallback starten."""
    inhalt = CMD_PATH.read_text(encoding="utf-8")

    assert 'if not "%EXIT_CODE%"=="0" (' in inhalt
    assert 'if not "%EXIT_CODE%"=="42" if not "%EXIT_CODE%"=="1223" if not "%EXIT_CODE%"=="16001" (' in inhalt
    assert 'PowerShell-Launcher meldete Exit-Code %EXIT_CODE%. Versuche Python-Direktstart.' in inhalt
    assert 'goto run_python_fallback' in inhalt


def test_cmd_launcher_erkennt_doppelklick_und_startet_persistente_konsole() -> None:
    """Bei cmd /c-Start muss der Launcher in eine persistente Konsole wechseln."""
    inhalt = CMD_PATH.read_text(encoding="utf-8")

    assert 'set "SHOULD_PERSIST=1"' in inhalt
    assert 'Doppelklick-Start erkannt: Neustart in persistenter Konsole (cmd /k).' in inhalt
    assert 'start "SystemManager-SageHelper Installer" cmd /k ""%SCRIPT_PATH%" --internal-persist --pause"' in inhalt
