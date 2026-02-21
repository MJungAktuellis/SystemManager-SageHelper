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


def test_cmd_launcher_hat_fallback_logstrategie_bei_unbeschreibbarem_projektpfad() -> None:
    """Prüft, dass bei fehlender Schreibbarkeit auf LOCALAPPDATA-Logs gewechselt wird."""
    inhalt = CMD_PATH.read_text(encoding="utf-8")

    assert 'set "LOG_WRITE_TEST=%LOG_DIR%\\.__write_test_%RANDOM%%RANDOM%.tmp"' in inhalt
    assert 'break>"%LOG_WRITE_TEST%" 2>nul' in inhalt
    assert 'if errorlevel 1 goto activate_log_fallback' in inhalt
    assert 'set "LOG_DIR=%LOCALAPPDATA%\\SystemManager-SageHelper\\logs"' in inhalt
    assert 'set "LOG_PATH_FALLBACK_ACTIVE=1"' in inhalt


def test_cmd_launcher_zeigt_aktiven_logpfad_und_fallback_warnung_sichtbar_an() -> None:
    """Stellt sicher, dass der aktive Logpfad und der Warnhinweis sichtbar ausgegeben werden."""
    inhalt = CMD_PATH.read_text(encoding="utf-8")

    assert 'echo [HINWEIS] Launcher-Logdatei: %LAUNCHER_LOG_REL%' in inhalt
    assert 'echo [HINWEIS] Vollstaendiger Pfad: %LAUNCHER_LOG%' in inhalt
    assert 'echo [WARN] Fallback-Logpfad aktiv: %LAUNCHER_LOG%' in inhalt
    assert 'echo [WARN] Fallback-Logpfad aktiv: %LAUNCHER_LOG%>>"%LAUNCHER_LOG%"' in inhalt
