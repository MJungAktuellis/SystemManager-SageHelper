# Installationsassistent – PowerShell dient als kanonischer Launcher für die Python-Orchestrierung.
[CmdletBinding()]
Param()

# Hinweis zur Kompatibilität: Alte Windows-Codepages stellen Emojis oft fehlerhaft dar.
# Deshalb verwenden wir bewusst ASCII-Textpräfixe ([OK], [WARN], [FEHLER], Hinweis:).

function Resolve-LauncherLogPath {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    # Primärer Zielpfad liegt im Repository, damit Logs direkt mit dem Projekt zusammenliegen.
    $primaryLogDir = Join-Path $RepoRoot "logs"

    # Fallback-Pfad bevorzugt LOCALAPPDATA; falls nicht verfügbar, wird ein Home-basiertes Verzeichnis genutzt.
    $localAppData = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($localAppData)) {
        $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
    }

    if ([string]::IsNullOrWhiteSpace($localAppData)) {
        $localAppData = Join-Path $HOME ".systemmanager-sagehelper"
    }

    $fallbackLogDir = Join-Path $localAppData "SystemManager-SageHelper\logs"
    $logFileName = "install_assistant_ps.log"

    $candidateTargets = @(
        @{ Directory = $primaryLogDir; Source = "repo"; UsedFallback = $false },
        @{ Directory = $fallbackLogDir; Source = "fallback"; UsedFallback = $true }
    )

    $lastErrorMessage = $null
    foreach ($candidate in $candidateTargets) {
        try {
            if (-not (Test-Path -LiteralPath $candidate.Directory)) {
                New-Item -ItemType Directory -Path $candidate.Directory -Force -ErrorAction Stop | Out-Null
            }

            $logPath = Join-Path $candidate.Directory $logFileName
            [System.IO.File]::AppendAllText($logPath, "")

            return [PSCustomObject]@{
                LogDir = $candidate.Directory
                PsLog = $logPath
                Source = $candidate.Source
                UsedFallback = $candidate.UsedFallback
            }
        }
        catch {
            $lastErrorMessage = $_.Exception.Message
        }
    }

    throw "Kein beschreibbarer Logpfad verfügbar. Letzter Fehler: $lastErrorMessage"
}

# Fruehe Initialisierung: Diese Pfade muessen bereits vor der Admin-Pruefung verfuegbar sein,
# damit auch der Nicht-Admin-/UAC-Pfad sauber protokolliert wird.
$script:RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$resolvedLogPath = Resolve-LauncherLogPath -RepoRoot $script:RepoRoot
$script:LogDir = $resolvedLogPath.LogDir
$script:PsLog = $resolvedLogPath.PsLog
if ($resolvedLogPath.UsedFallback) {
    Write-Host "[WARN] Aktiver Logpfad (Fallback): $script:PsLog"
}
else {
    Write-Host "[INFO] Aktiver Logpfad: $script:PsLog"
}
Add-Content -Path $script:PsLog -Value ("==== [" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] Start scripts/install_assistant.ps1 ====")

# Exit-Code-Konstanten fuer nachvollziehbare Automatisierung und eindeutige Launcher-Meldungen.
$ExitCodeElevationTriggered = 42
$ExitCodeUacCancelled = 1223
$ExitCodeElevationFailed = 16001

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

function Invoke-InstallerExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StrategyLabel,
        [int]$TimeoutSeconds = 600
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        Write-PsLog -Category "WARN" -Cause "INSTALLER_DATEI_FEHLT" -Candidate $StrategyLabel -Message "Installer-Datei wurde nicht gefunden: $FilePath"
        return @{ Success = $false; ExitCode = $null; Reason = "Datei nicht gefunden" }
    }

    Write-Host "[INFO] Starte Installationsstrategie '$StrategyLabel' mit '$FilePath'."
    Write-PsLog -Category "INFO" -Cause "INSTALLATIONSSTRATEGIE_START" -Candidate $StrategyLabel -Message "Datei: $FilePath | Argumente: $($Arguments -join ' ')"

    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru -NoNewWindow
    if ($null -eq $process) {
        Write-PsLog -Category "ERROR" -Cause "INSTALLER_START_FEHLGESCHLAGEN" -Candidate $StrategyLabel -Message "Prozessstart lieferte kein Prozessobjekt."
        return @{ Success = $false; ExitCode = $null; Reason = "Prozessstart fehlgeschlagen" }
    }

    # Einige Installer ignorieren -Wait; deshalb prüfen wir zusätzlich aktiv auf Timeout.
    if (-not $process.HasExited) {
        $waitResult = $process.WaitForExit($TimeoutSeconds * 1000)
        if (-not $waitResult) {
            $process.Kill()
            Write-PsLog -Category "ERROR" -Cause "INSTALLER_TIMEOUT" -Candidate $StrategyLabel -Message "Timeout nach $TimeoutSeconds Sekunden, Prozess wurde beendet."
            return @{ Success = $false; ExitCode = $null; Reason = "Timeout" }
        }
    }

    $exitCode = $process.ExitCode
    Write-PsLog -Category "INFO" -Cause "INSTALLER_BEENDET" -Candidate $StrategyLabel -ExitCode $exitCode -Message "Strategie beendet."

    if ($exitCode -in @(0, 1641, 3010)) {
        return @{ Success = $true; ExitCode = $exitCode; Reason = "Erfolgreich" }
    }

    return @{ Success = $false; ExitCode = $exitCode; Reason = "ExitCode $exitCode" }
}

function Find-LocalPythonInstaller {
    param([string]$RepoRoot)

    $searchRoots = @(
        Join-Path $RepoRoot "scripts\bootstrap",
        Join-Path $RepoRoot "installer\bootstrap"
    )

    $patterns = @("python*.exe", "python*.msi")
    foreach ($root in $searchRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            Write-PsLog -Category "INFO" -Cause "LOKALER_INSTALLER_PFAD_FEHLT" -Candidate "lokaler-installer" -Message "Pfad fehlt: $root"
            continue
        }

        $matches = Get-ChildItem -Path $root -File -ErrorAction SilentlyContinue | Where-Object {
            $name = $_.Name.ToLowerInvariant()
            [bool]($patterns | Where-Object { $name -like $_ } | Select-Object -First 1)
        } | Sort-Object LastWriteTime -Descending

        if ($matches) {
            $selected = $matches | Select-Object -First 1
            Write-PsLog -Category "INFO" -Cause "LOKALER_INSTALLER_GEFUNDEN" -Candidate "lokaler-installer" -Message "Verwende Datei: $($selected.FullName)"
            return $selected.FullName
        }
    }

    return $null
}

function Get-InstallerArguments {
    param([string]$InstallerPath)

    $extension = [System.IO.Path]::GetExtension($InstallerPath).ToLowerInvariant()
    if ($extension -eq ".msi") {
        return @("/i", "`"$InstallerPath`"", "/qn", "/norestart")
    }

    # Offizielle Python-EXE-Installer-Parameter für eine stille Installation.
    return @("/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_launcher=1")
}

function Test-DownloadAllowed {
    # Standardmäßig aus Sicherheitsgründen deaktiviert. Aktivierung nur bewusst per Umgebungsvariable.
    return $env:SYSTEMMANAGER_ALLOW_PYTHON_DOWNLOAD -eq "1"
}

function Invoke-DownloadWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Destination,
        [int]$RetryCount = 3,
        [int]$TimeoutSeconds = 120
    )

    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        try {
            Write-PsLog -Category "INFO" -Cause "DOWNLOAD_VERSUCH" -Candidate "online-download" -Message "Versuch $attempt/${RetryCount}: $Url"
            $progressPreferenceBackup = $ProgressPreference
            $ProgressPreference = "SilentlyContinue"
            Invoke-WebRequest -Uri $Url -OutFile $Destination -TimeoutSec $TimeoutSeconds -UseBasicParsing
            $ProgressPreference = $progressPreferenceBackup
            return $true
        }
        catch {
            $ProgressPreference = $progressPreferenceBackup
            Write-PsLog -Category "WARN" -Cause "DOWNLOAD_FEHLER" -Candidate "online-download" -Message "Versuch $attempt fehlgeschlagen: $($_.Exception.Message)"
            Start-Sleep -Seconds ([Math]::Min(5 * $attempt, 15))
        }
    }

    return $false
}

function Test-FileHashMatch {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    $actualHash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash
    $match = $actualHash.Equals($ExpectedSha256, [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $match) {
        Write-PsLog -Category "ERROR" -Cause "HASH_PRUEFUNG_FEHLGESCHLAGEN" -Candidate "online-download" -Message "Erwartet: $ExpectedSha256 | Ist: $actualHash"
    }
    return $match
}

function Resolve-PythonAfterInstall {
    param(
        [array]$Candidates,
        [string]$StrategyLabel
    )

    Refresh-ProcessPath
    $resolved = Resolve-PythonLauncher -Candidates $Candidates
    if ($resolved) {
        Write-PsLog -Category "INFO" -Cause "PYTHON_NACH_INSTALLATION_GEFUNDEN" -Candidate $StrategyLabel -Message "Launcher: $($resolved.Label)"
        return $resolved
    }

    Write-PsLog -Category "WARN" -Cause "PYTHON_NACH_INSTALLATION_NICHT_GEFUNDEN" -Candidate $StrategyLabel -Message "Trotz Installation kein Launcher gefunden."
    return $null
}

function Ensure-PythonAvailable {
    param(
        [array]$Candidates,
        [string]$RepoRoot
    )

    $resolved = Resolve-PythonLauncher -Candidates $Candidates
    if ($resolved) {
        Write-PsLog -Category "INFO" -Cause "PYTHON_BEREITS_VERFUEGBAR" -Candidate $resolved.Label -Message "Python-Launcher bereits gefunden."
        return $resolved
    }

    Write-Host "[WARN] Kein Python-Launcher gefunden. Starte Bootstrap-Installation (winget -> choco -> lokal -> online optional)."
    Write-PsLog -Category "WARN" -Cause "PYTHON_FEHLT" -Message "Kein Python-Launcher gefunden."

    $strategyErrors = New-Object System.Collections.Generic.List[string]

    $installSucceeded = Invoke-PythonInstallAttempt -Installer "winget" -Command "winget" -Arguments @("install", "--id", "Python.Python.3.11", "-e", "--accept-package-agreements", "--accept-source-agreements")
    if ($installSucceeded) {
        $resolved = Resolve-PythonAfterInstall -Candidates $Candidates -StrategyLabel "winget"
        if ($resolved) { return $resolved }
        $strategyErrors.Add("winget: Installation erfolgreich, aber Launcher nicht auflösbar") | Out-Null
    }
    else {
        $strategyErrors.Add("winget: nicht verfügbar oder fehlgeschlagen") | Out-Null
    }

    $installSucceeded = Invoke-PythonInstallAttempt -Installer "choco" -Command "choco" -Arguments @("install", "python", "--yes", "--no-progress")
    if ($installSucceeded) {
        $resolved = Resolve-PythonAfterInstall -Candidates $Candidates -StrategyLabel "choco"
        if ($resolved) { return $resolved }
        $strategyErrors.Add("choco: Installation erfolgreich, aber Launcher nicht auflösbar") | Out-Null
    }
    else {
        $strategyErrors.Add("choco: nicht verfügbar oder fehlgeschlagen") | Out-Null
    }

    $localInstaller = Find-LocalPythonInstaller -RepoRoot $RepoRoot
    if ($localInstaller) {
        $installerArguments = Get-InstallerArguments -InstallerPath $localInstaller
        if ([System.IO.Path]::GetExtension($localInstaller).ToLowerInvariant() -eq ".msi") {
            $execution = Invoke-InstallerExecutable -FilePath "msiexec.exe" -Arguments $installerArguments -StrategyLabel "lokaler-msi-installer"
        }
        else {
            $execution = Invoke-InstallerExecutable -FilePath $localInstaller -Arguments $installerArguments -StrategyLabel "lokaler-exe-installer"
        }

        if ($execution.Success) {
            $resolved = Resolve-PythonAfterInstall -Candidates $Candidates -StrategyLabel "lokaler-installer"
            if ($resolved) { return $resolved }
            $strategyErrors.Add("lokaler Installer: ExitCode $($execution.ExitCode), aber Launcher nicht auflösbar") | Out-Null
        }
        else {
            $strategyErrors.Add("lokaler Installer: $($execution.Reason)") | Out-Null
        }
    }
    else {
        $strategyErrors.Add("lokaler Installer: keine Datei in scripts/bootstrap oder installer/bootstrap gefunden") | Out-Null
    }

    if (Test-DownloadAllowed) {
        $downloadUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $expectedHash = $env:SYSTEMMANAGER_PYTHON_BOOTSTRAP_SHA256
        $downloadTarget = Join-Path $env:TEMP "python-3.11.9-amd64.exe"

        if ([string]::IsNullOrWhiteSpace($expectedHash)) {
            $strategyErrors.Add("online-download: übersprungen, da SYSTEMMANAGER_PYTHON_BOOTSTRAP_SHA256 fehlt") | Out-Null
            Write-PsLog -Category "WARN" -Cause "DOWNLOAD_OHNE_HASH_VERBOTEN" -Candidate "online-download" -Message "Download aktiviert, aber keine Hash-Vorgabe gesetzt."
        }
        else {
            $downloadOk = Invoke-DownloadWithRetry -Url $downloadUrl -Destination $downloadTarget
            if ($downloadOk -and (Test-FileHashMatch -FilePath $downloadTarget -ExpectedSha256 $expectedHash)) {
                $execution = Invoke-InstallerExecutable -FilePath $downloadTarget -Arguments (Get-InstallerArguments -InstallerPath $downloadTarget) -StrategyLabel "online-download-installer"
                if ($execution.Success) {
                    $resolved = Resolve-PythonAfterInstall -Candidates $Candidates -StrategyLabel "online-download"
                    if ($resolved) { return $resolved }
                    $strategyErrors.Add("online-download: ExitCode $($execution.ExitCode), aber Launcher nicht auflösbar") | Out-Null
                }
                else {
                    $strategyErrors.Add("online-download: Installer fehlgeschlagen ($($execution.Reason))") | Out-Null
                }
            }
            else {
                $strategyErrors.Add("online-download: Download oder Hash-Prüfung fehlgeschlagen") | Out-Null
            }
        }
    }
    else {
        $strategyErrors.Add("online-download: per Richtlinie deaktiviert (SYSTEMMANAGER_ALLOW_PYTHON_DOWNLOAD!=1)") | Out-Null
    }

    $errorMessage = "Keine Installationsstrategie erfolgreich: " + ($strategyErrors -join " | ")
    Write-PsLog -Category "ERROR" -Cause "PYTHON_BOOTSTRAP_FEHLGESCHLAGEN" -Message $errorMessage
    Write-Host "[FEHLER] Python-Bootstrap fehlgeschlagen. Details: $errorMessage"
    return $null
}

if (-not (Test-Admin)) {
    Write-Host "[INFO] Skript läuft nicht mit Administratorrechten. Starte neu als Admin..."
    Write-PsLog -Category "WARN" -Cause "ADMINRECHTE_FEHLEN" -Message "Neustart mit Erhoehung wird angefordert." -Candidate "Start-Process -Verb RunAs"
    try {
        # Bevorzugt den expliziten Pfad zur Windows PowerShell, um PATH-/Alias-Probleme zu vermeiden.
        # Fallback auf den Kommando-Namen, falls die Standardinstallation unerwartet fehlt.
        $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        if (-not (Test-Path -LiteralPath $psExe)) {
            $psExe = "powershell.exe"
        }

        # Wichtig: Argumente als Array übergeben, damit Pfade mit Leerzeichen,
        # Klammern oder Sonderzeichen (z. B. Apostrophen) sicher gequotet werden.
        # Zusätzlich setzen wir das Arbeitsverzeichnis explizit auf das Repo,
        # damit der erhöhte Prozess zuverlässig dieselben relativen Pfade nutzt.
        $elevationArguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $PSCommandPath
        )
        $elevatedProcess = Start-Process -FilePath $psExe -ArgumentList $elevationArguments -WorkingDirectory $script:RepoRoot -Verb RunAs -PassThru -ErrorAction Stop
        if ($null -eq $elevatedProcess) {
            Write-Host "[FEHLER] Erhoehung konnte nicht gestartet werden. Bitte PowerShell als Administrator oeffnen und das Skript erneut starten."
            Write-PsLog -Category "ERROR" -Cause "ELEVATION_START_OHNE_PROZESS" -ExitCode $ExitCodeElevationFailed -Message "Start-Process lieferte kein Prozessobjekt." -Candidate "PowerShell als Administrator manuell starten"
            Write-PsLog -Category "ERROR" -Cause "SCRIPT_EXIT" -ExitCode $ExitCodeElevationFailed -Message "Abbruch ohne gestarteten Elevated-Prozess. Nächster Schritt: manuell mit Adminrechten starten."
            exit $ExitCodeElevationFailed
        }

        Write-Host "[HINWEIS] UAC-Dialog wurde gestartet. Bitte bestaetigen Sie den Admin-Start im neuen Fenster."
        Write-PsLog -Category "INFO" -Cause "ELEVATION_GESTARTET" -ExitCode $ExitCodeElevationTriggered -Message "Elevated-Prozess wurde erfolgreich gestartet (PID $($elevatedProcess.Id))." -Candidate "UAC bestaetigen und im neuen Fenster fortfahren"
        Write-PsLog -Category "INFO" -Cause "SCRIPT_EXIT" -ExitCode $ExitCodeElevationTriggered -Message "Aktuelle Instanz beendet sich planmaessig nach erfolgreichem Elevation-Start."
        exit $ExitCodeElevationTriggered
    }
    catch [System.ComponentModel.Win32Exception] {
        if ($_.Exception.NativeErrorCode -eq 1223) {
            Write-Host "[FEHLER] UAC-Abbruch erkannt (Code 1223). Bitte Installer erneut starten und die Rueckfrage mit 'Ja' bestaetigen."
            Write-PsLog -Category "ERROR" -Cause "UAC_ABGEBROCHEN" -ExitCode $ExitCodeUacCancelled -Message "Benutzer hat den UAC-Dialog abgebrochen." -Candidate "Installer erneut starten und UAC bestaetigen"
            Write-PsLog -Category "ERROR" -Cause "SCRIPT_EXIT" -ExitCode $ExitCodeUacCancelled -Message "Abbruch durch Benutzeraktion. Nächster Schritt: erneut ausfuehren und UAC bestaetigen."
            exit $ExitCodeUacCancelled
        }

        Write-Host "[FEHLER] Erhoehung fehlgeschlagen: $($_.Exception.Message)"
        Write-PsLog -Category "ERROR" -Cause "ELEVATION_START_FEHLGESCHLAGEN" -ExitCode $ExitCodeElevationFailed -Message "Win32Exception beim Elevation-Start: $($_.Exception.Message)" -Candidate "PowerShell als Administrator manuell starten"
        Write-PsLog -Category "ERROR" -Cause "SCRIPT_EXIT" -ExitCode $ExitCodeElevationFailed -Message "Abbruch nach fehlgeschlagenem Elevation-Start."
        exit $ExitCodeElevationFailed
    }
    catch {
        Write-Host "[FEHLER] Unerwarteter Fehler beim Elevation-Start: $($_.Exception.Message)"
        Write-PsLog -Category "ERROR" -Cause "ELEVATION_START_UNERWARTET" -ExitCode $ExitCodeElevationFailed -Message "Unerwartete Ausnahme: $($_.Exception.Message)" -Candidate "PowerShell als Administrator manuell starten"
        Write-PsLog -Category "ERROR" -Cause "SCRIPT_EXIT" -ExitCode $ExitCodeElevationFailed -Message "Abbruch nach unerwartetem Fehler im Elevation-Pfad."
        exit $ExitCodeElevationFailed
    }
}

Write-Host "=== SystemManager-SageHelper: Installations-Launcher ==="
Write-Host "[INFO] Kanonischer Einstieg: scripts/install_assistant.ps1 -> scripts/install.py -> systemmanager_sagehelper.installer"

$RepoRoot = $script:RepoRoot
$InstallScript = Join-Path $RepoRoot "scripts\install.py"
$LogDir = $script:LogDir
$PsLog = $script:PsLog

# Bevorzugte Interpreter-Reihenfolge für den Start der Python-Orchestrierung.
$PythonCandidates = Get-PythonCandidates
$resolvedLauncher = Ensure-PythonAvailable -Candidates $PythonCandidates -RepoRoot $RepoRoot
if (-not $resolvedLauncher) {
    Write-Host "[FEHLER] Python konnte nicht automatisch installiert oder gefunden werden."
    Write-Host "Konkrete Schritte:"
    Write-Host "  1) winget install --id Python.Python.3.11 -e"
    Write-Host "  2) Falls winget fehlt: choco install python --yes"
    Write-Host "  3) Alternativ lokalen Installer in scripts/bootstrap oder installer/bootstrap ablegen."
    Write-Host "  4) Optional Online-Download erlauben: SYSTEMMANAGER_ALLOW_PYTHON_DOWNLOAD=1 und SYSTEMMANAGER_PYTHON_BOOTSTRAP_SHA256 setzen."
    Write-Host "  5) Danach erneut 'Install-SystemManager-SageHelper.cmd' starten."
    Write-PsLog -Category "ERROR" -Cause "PYTHON_FEHLT" -Message "Python nicht verfügbar und automatische Installation nicht erfolgreich."
    Write-PsLog -Category "ERROR" -Cause "SCRIPT_EXIT" -ExitCode 1 -Message "Abbruch wegen fehlender Python-Laufzeit. Nächster Schritt: Python manuell installieren oder Bootstrap-Vorgaben setzen."
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
    Write-PsLog -Category "ERROR" -Cause "SCRIPT_EXIT" -ExitCode 1 -Message "Abbruch wegen fehlgeschlagener Python-Orchestrierung. Nächster Schritt: logs prüfen und scripts/install.py manuell testen."
    exit 1
}

Add-Content -Path $PsLog -Value ("==== [" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] Ende scripts/install_assistant.ps1 ====")
Write-Host "[OK] Installationsprozess abgeschlossen."
