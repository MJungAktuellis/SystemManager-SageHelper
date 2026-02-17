# Installationsassistent – PowerShell dient nur als Launcher für die Python-Kernlogik.
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
Write-Host "[INFO] Standardpfad: GUI-Installer (scripts/install_gui.py)."

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallScript = Join-Path $RepoRoot "scripts\install_gui.py"

# Bevorzugte Interpreter-Reihenfolge für den Start der Python-Kernlogik.
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
    $arguments += @($InstallScript)

    Write-Host "[INFO] Starte Installer mit: $($candidate -join ' ') (GUI-Standard)"
    & $exe @arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        $launched = $true
        break
    }

    Write-Host "[WARN] Installer mit '$($candidate -join ' ')' beendet mit ExitCode $exitCode."
}

if (-not $launched) {
    Write-Host "[FEHLER] Fehler: Konnte den Python-basierten Installer nicht erfolgreich starten."
    Write-Host "Hinweis: Bitte prüfen Sie die Python-Installation oder führen Sie scripts/install_gui.py bzw. scripts/install.py manuell aus."
    exit 1
}

Write-Host "[OK] Installationsprozess abgeschlossen."
