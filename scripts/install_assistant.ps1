<#
.SYNOPSIS
    Gefuehrter One-Click-Installer fuer Windows-Server.
.DESCRIPTION
    Installiert bei Bedarf Git und Python (ueber winget/choco) und fuehrt danach
    den Python-Installationsassistenten des Projekts aus.
#>

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonInstaller = Join-Path $repoRoot "scripts\install.py"
$logDirectory = Join-Path $repoRoot "logs"
$psLogFile = Join-Path $logDirectory "install_assistant_ps.log"

if (-not (Test-Path $logDirectory)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

Start-Transcript -Path $psLogFile -Append | Out-Null

try {
    Write-Host "=== SystemManager-SageHelper: One-Click-Installer ===" -ForegroundColor Cyan
    Write-Host "[INFO] PowerShell-Log: $psLogFile" -ForegroundColor DarkCyan

    if (-not (Test-Path $pythonInstaller)) {
        throw "install.py wurde nicht gefunden: $pythonInstaller"
    }

    function Get-PythonCommand {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            return @{ Command = "py"; Args = @("-3") }
        }

        if (Get-Command python -ErrorAction SilentlyContinue) {
            return @{ Command = "python"; Args = @() }
        }

        return $null
    }

    $pythonCmd = Get-PythonCommand

    if (-not $pythonCmd) {
        Write-Host "[INFO] Kein Python gefunden. Versuche automatische Installation..." -ForegroundColor Yellow

        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install --id Python.Python.3.11 --exact --source winget --accept-package-agreements --accept-source-agreements --silent
        }
        elseif (Get-Command choco -ErrorAction SilentlyContinue) {
            choco install python -y
        }
        else {
            throw "Weder winget noch choco verfuegbar. Bitte Python 3.11+ manuell installieren."
        }

        $pythonCmd = Get-PythonCommand
        if (-not $pythonCmd) {
            throw "Python konnte nicht ermittelt werden. Bitte Shell neu starten und erneut ausfuehren."
        }
    }

    Write-Host "[INFO] Starte Python-Installer..." -ForegroundColor Green
    & $pythonCmd.Command @($pythonCmd.Args + @($pythonInstaller))

    if ($LASTEXITCODE -ne 0) {
        throw "Python-Installer wurde mit Exit-Code $LASTEXITCODE beendet."
    }

    Write-Host "[OK] Installation abgeschlossen." -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "[FEHLER] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "[HINWEIS] Bitte Logdateien teilen:" -ForegroundColor Yellow
    Write-Host "  - $psLogFile" -ForegroundColor Yellow
    Write-Host "  - $(Join-Path $repoRoot 'logs\install_assistant.log')" -ForegroundColor Yellow
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
