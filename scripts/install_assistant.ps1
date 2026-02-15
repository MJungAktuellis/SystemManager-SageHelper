<#
.SYNOPSIS
    Gefuehrter One-Click-Installer fuer Windows-Server.
.DESCRIPTION
    Installiert bei Bedarf Git und Python (ueber winget/choco) und fuehrt danach
    den Python-Installationsassistenten des Projekts aus.
#>

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $PSScriptRoot
$pythonInstaller = Join-Path $scriptRoot "scripts\install.py"

Write-Host "=== SystemManager-SageHelper: One-Click-Installer ===" -ForegroundColor Cyan

if (-not (Test-Path $pythonInstaller)) {
    Write-Host "[FEHLER] install.py wurde nicht gefunden: $pythonInstaller" -ForegroundColor Red
    exit 1
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py -3"
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
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
        Write-Host "[FEHLER] Weder winget noch choco verfuegbar. Bitte Python 3.11+ manuell installieren." -ForegroundColor Red
        exit 1
    }

    $pythonCmd = Get-PythonCommand
    if (-not $pythonCmd) {
        Write-Host "[FEHLER] Python konnte nicht ermittelt werden. Bitte Shell neu starten und erneut ausfuehren." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[INFO] Starte Python-Installer: $pythonCmd $pythonInstaller" -ForegroundColor Green
Invoke-Expression "$pythonCmd \"$pythonInstaller\""

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FEHLER] Installation wurde mit Exit-Code $LASTEXITCODE beendet." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[OK] Installation abgeschlossen." -ForegroundColor Green
