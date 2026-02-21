"""Regressionstests für den PowerShell-Installer-Launcher."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PS1_PATH = REPO_ROOT / "scripts" / "install_assistant.ps1"


def test_elevation_verwendet_argument_array_und_repo_workdir() -> None:
    """Der UAC-Neustart soll robust gequotet und im Repo-Kontext ausgeführt werden."""
    inhalt = PS1_PATH.read_text(encoding="utf-8")

    assert "$elevationArguments = @(" in inhalt
    assert '"-File", $PSCommandPath' in inhalt
    assert "-ArgumentList $elevationArguments" in inhalt
    assert "-WorkingDirectory $script:RepoRoot" in inhalt


def test_logpfad_resolve_mit_fallback_und_sichtbarer_ausgabe() -> None:
    """Der Launcher soll einen robusten Logpfad mit dokumentiertem Fallback verwenden."""
    inhalt = PS1_PATH.read_text(encoding="utf-8")

    assert "function Resolve-LauncherLogPath" in inhalt
    assert "$primaryLogDir = Join-Path $RepoRoot \"logs\"" in inhalt
    assert "$fallbackLogDir = Join-Path $localAppData \"SystemManager-SageHelper\\logs\"" in inhalt
    assert "$resolvedLogPath = Resolve-LauncherLogPath -RepoRoot $script:RepoRoot" in inhalt
    assert "$script:PsLog = $resolvedLogPath.PsLog" in inhalt
    assert 'Write-Host "[WARN] Aktiver Logpfad (Fallback): $script:PsLog"' in inhalt
    assert 'Write-Host "[INFO] Aktiver Logpfad: $script:PsLog"' in inhalt


def test_elevation_pfad_protokolliert_aktiven_logpfad_und_markerdatei() -> None:
    """Der Elevation-Pfad soll Logpfad sichtbar ausgeben und eine Session-Markerdatei erzeugen."""
    inhalt = PS1_PATH.read_text(encoding="utf-8")

    assert 'function New-LauncherSessionMarker' in inhalt
    assert 'Write-Host "[HINWEIS] Aktiver Logpfad der erhöhten Instanz: $script:PsLog"' in inhalt
    assert 'Write-PsLog -Category "INFO" -Cause "ELEVATION_GESTARTET" -Message "Aktiver Logpfad der erhöhten Instanz: $script:PsLog"' in inhalt
    assert '$sessionMarkerPath = New-LauncherSessionMarker -LogDirectory $script:LogDir -ProcessId $elevatedProcess.Id' in inhalt


def test_ps1_hat_offline_proxy_adminskip_und_venv_initialisierung() -> None:
    """Der Launcher muss Offline/Proxy/Adminskip unterstützen und eine venv anlegen können."""
    inhalt = PS1_PATH.read_text(encoding="utf-8")

    assert "[switch]$Offline" in inhalt
    assert "[switch]$SkipAdminCheck" in inhalt
    assert "[string]$ProxyUrl" in inhalt
    assert "function Initialize-PythonEnvironment" in inhalt
    assert 'Join-Path $RepoRoot ".venv"' in inhalt
    assert 'Write-PsLog -Category "INFO" -Cause "REQUIREMENTS_INSTALLIERT"' in inhalt
    assert 'Write-PsLog -Category "INFO" -Cause "ROLLBACK_VENV_ERFOLGREICH"' in inhalt
    assert 'elseif ($SkipAdminCheck) {' in inhalt


def test_ps1_prueft_python_mindestversion_3_8() -> None:
    """Python-Launcher unterhalb der Mindestversion 3.8 dürfen nicht genutzt werden."""
    inhalt = PS1_PATH.read_text(encoding="utf-8")

    assert "function Test-PythonVersionSupported" in inhalt
    assert '[Version]"3.8.0"' in inhalt
    assert 'PYTHON_VERSION_ZU_ALT' in inhalt
