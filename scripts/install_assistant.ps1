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

function Write-PsLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$Category = "INFO",
        [string]$Cause,
        [string]$Candidate,
        [Nullable[int]]$ExitCode
    )

    $parts = @("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "]", "[" + $Category + "]")
    if ($Cause) {
        $parts += "[URSACHE:$Cause]"
    }
    if ($Candidate) {
        $parts += "[KANDIDAT:$Candidate]"
    }
    if ($null -ne $ExitCode) {
        $parts += "[EXITCODE:$ExitCode]"
    }
    $parts += $Message
    Add-Content -Path $script:PsLog -Value ($parts -join " ")
}

function Get-PythonCandidates {
    # Reihenfolge spiegelt die bevorzugte Startstrategie wider.
    return @(
        @{ Exe = "py"; Args = @("-3"); Label = "py -3" },
        @{ Exe = "python"; Args = @(); Label = "python" },
        @{ Exe = "python3"; Args = @(); Label = "python3" }
    )
}

function Resolve-PythonLauncher {
    param([array]$Candidates)

    foreach ($candidate in $Candidates) {
        $cmd = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if ($cmd) {
            return $candidate
        }
    }

    return $null
}

function Refresh-ProcessPath {
    # Nach Installer-Läufen die PATH-Variablen des aktuellen Prozesses neu zusammensetzen,
    # damit frisch installierte Python-Launcher ohne Neustart auffindbar sind.
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $combinedPath = @($machinePath, $userPath) -join ";"
    if (-not [string]::IsNullOrWhiteSpace($combinedPath)) {
        $env:Path = $combinedPath
    }
}

function Invoke-PythonInstallAttempt {
    param(
        [Parameter(Mandatory = $true)][string]$Installer,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $installerCommand = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $installerCommand) {
        Write-Host "[WARN] '$Installer' ist auf diesem System nicht verfügbar."
        Write-PsLog -Category "WARN" -Cause "INSTALLER_NICHT_VERFUEGBAR" -Candidate $Installer -Message "Installer nicht gefunden."
        return $false
    }

    Write-Host "[INFO] Versuche Python-Installation mit $Installer ..."
    & $Command @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-PsLog -Category "INFO" -Cause "PYTHON_INSTALLATION_ERFOLGREICH" -Candidate $Installer -ExitCode $exitCode -Message "Python-Installation erfolgreich abgeschlossen."
        return $true
    }

    Write-Host "[WARN] Python-Installation mit '$Installer' fehlgeschlagen (ExitCode $exitCode)."
    Write-PsLog -Category "ERROR" -Cause "INSTALLER_FEHLGESCHLAGEN" -Candidate $Installer -ExitCode $exitCode -Message "Installer-Lauf fehlgeschlagen."
    return $false
}

function Ensure-PythonAvailable {
    param([array]$Candidates)

    $resolved = Resolve-PythonLauncher -Candidates $Candidates
    if ($resolved) {
        Write-PsLog -Category "INFO" -Cause "PYTHON_BEREITS_VERFUEGBAR" -Candidate $resolved.Label -Message "Python-Launcher bereits gefunden."
        return $resolved
    }

    Write-Host "[WARN] Kein Python-Launcher gefunden. Starte Bootstrap-Installation (winget -> choco)."
    Write-PsLog -Category "WARN" -Cause "PYTHON_FEHLT" -Message "Kein Python-Launcher gefunden."

    $installSucceeded = Invoke-PythonInstallAttempt -Installer "winget" -Command "winget" -Arguments @("install", "--id", "Python.Python.3.11", "-e", "--accept-package-agreements", "--accept-source-agreements")
    if (-not $installSucceeded) {
        $installSucceeded = Invoke-PythonInstallAttempt -Installer "choco" -Command "choco" -Arguments @("install", "python", "--yes", "--no-progress")
    }

    if (-not $installSucceeded) {
        return $null
    }

    Refresh-ProcessPath
    return Resolve-PythonLauncher -Candidates $Candidates
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
$PythonCandidates = Get-PythonCandidates
$resolvedLauncher = Ensure-PythonAvailable -Candidates $PythonCandidates
if (-not $resolvedLauncher) {
    Write-Host "[FEHLER] Python konnte nicht automatisch installiert oder gefunden werden."
    Write-Host "Konkrete Schritte:"
    Write-Host "  1) winget install --id Python.Python.3.11 -e"
    Write-Host "  2) Falls winget fehlt: choco install python --yes"
    Write-Host "  3) Danach erneut 'Install-SystemManager-SageHelper.cmd' starten."
    Write-PsLog -Category "ERROR" -Cause "PYTHON_FEHLT" -Message "Python nicht verfügbar und automatische Installation nicht erfolgreich."
    exit 1
}

$launched = $false
foreach ($candidate in $PythonCandidates) {
    $exe = $candidate.Exe
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $cmd) {
        continue
    }

    $arguments = @($candidate.Args)
    # Standardmäßig GUI, mit robustem CLI-Fallback innerhalb von scripts/install.py.
    $arguments += @($InstallScript)

    Write-Host "[INFO] Starte Installer-Orchestrierung mit: $($candidate.Label)"
    & $exe @arguments
    $exitCode = $LASTEXITCODE
    Write-PsLog -Category "INFO" -Cause "INSTALL_SCRIPT_EXIT" -Candidate $candidate.Label -ExitCode $exitCode -Message "scripts/install.py ausgeführt."
    if ($exitCode -eq 0) {
        $launched = $true
        break
    }

    Write-Host "[WARN] Installer mit '$($candidate.Label)' beendet mit ExitCode $exitCode."
    Write-PsLog -Category "ERROR" -Cause "PYTHON_ORCHESTRIERUNG_FEHLGESCHLAGEN" -Candidate $candidate.Label -ExitCode $exitCode -Message "scripts/install.py wurde mit Fehler beendet."
}

if (-not $launched) {
    Write-Host "[FEHLER] Fehler: Konnte den Python-basierten Installer nicht erfolgreich starten."
    Write-Host "Hinweis: Bitte prüfen Sie die Python-Installation oder führen Sie scripts/install.py manuell aus."
    Write-PsLog -Category "ERROR" -Cause "PYTHON_ORCHESTRIERUNG_FEHLGESCHLAGEN" -Message "Python-Orchestrierung konnte mit keinem Launcher erfolgreich beendet werden."
    exit 1
}

Add-Content -Path $PsLog -Value ("==== [" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] Ende scripts/install_assistant.ps1 ====")
Write-Host "[OK] Installationsprozess abgeschlossen."
