# Installationsassistent – PowerShell dient als kanonischer Launcher für die Python-Orchestrierung.
[CmdletBinding()]
Param()

# Hinweis zur Kompatibilität: Alte Windows-Codepages stellen Emojis oft fehlerhaft dar.
# Deshalb verwenden wir bewusst ASCII-Textpräfixe ([OK], [WARN], [FEHLER], Hinweis:).

function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "[INFO] Skript läuft nicht mit Administratorrechten. Starte neu als Admin..."
    Start-Process -FilePath "PowerShell" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host "=== SystemManager-SageHelper: Installations-Launcher ==="
Write-Host "[INFO] Kanonischer Einstieg: scripts/install_assistant.ps1 -> scripts/install.py -> systemmanager_sagehelper.installer"

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallScript = Join-Path $RepoRoot "scripts\install.py"
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$PsLog = Join-Path $LogDir "install_assistant_ps.log"
Add-Content -Path $PsLog -Value ("==== [" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] Start scripts/install_assistant.ps1 ====")

# Bevorzugte Interpreter-Reihenfolge für den Start der Python-Orchestrierung.
$PythonCandidates = @(
    @("py", "-3"),
    @("python"),
    @("python3")
)

$launched = $false
foreach ($candidate in $PythonCandidates) {
    $exe = $candidate[0]
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $cmd) {
        continue
    }

    $arguments = @()
    if ($candidate.Count -gt 1) {
        $arguments += $candidate[1..($candidate.Count - 1)]
    }
    # Standardmäßig GUI, mit robustem CLI-Fallback innerhalb von scripts/install.py.
    $arguments += @($InstallScript)

    Write-Host "[INFO] Starte Installer-Orchestrierung mit: $($candidate -join ' ')"
    & $exe @arguments
    $exitCode = $LASTEXITCODE
    Add-Content -Path $PsLog -Value ("Interpreter " + ($candidate -join " ") + " ExitCode=" + $exitCode)
    if ($exitCode -eq 0) {
        $launched = $true
        break
    }

    Write-Host "[WARN] Installer mit '$($candidate -join ' ')' beendet mit ExitCode $exitCode."
}

if (-not $launched) {
    Write-Host "[FEHLER] Fehler: Konnte den Python-basierten Installer nicht erfolgreich starten."
    Write-Host "Hinweis: Bitte prüfen Sie die Python-Installation oder führen Sie scripts/install.py manuell aus."
    Add-Content -Path $PsLog -Value "[FEHLER] Python-Orchestrierung konnte nicht gestartet werden."
    exit 1
}

Add-Content -Path $PsLog -Value ("==== [" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] Ende scripts/install_assistant.ps1 ====")
Write-Host "[OK] Installationsprozess abgeschlossen."
