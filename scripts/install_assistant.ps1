# Installationsassistent – Erzwinge Administratorrechte
[CmdletBinding()]
Param()

function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-Not (Test-Admin)) {
    Write-Host "[INFO] Skript läuft nicht mit Administratorrechten. Starte neu als Admin..."
    Start-Process -FilePath PowerShell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

Write-Host "[INFO] Skript läuft mit Administratorrechten. Fortfahren..."

# Python prüfen und ggf. installieren
Write-Host "=== SystemManager-SageHelper: One-Click-Installer ==="
Write-Host "[INFO] Prüfe, ob Python installiert ist..."
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Python ist nicht installiert. Starte automatische Installation..."

    $PythonInstallerUrl = "https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
    $InstallerPath = "$PSScriptRoot\\python-installer.exe"

    Write-Host "[INFO] Lade Python-Installer herunter..."
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $InstallerPath

    Write-Host "[INFO] Installiere Python..."
    Start-Process -FilePath $InstallerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -NoNewWindow -Wait

    python --version
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Fehler: Python konnte nicht installiert werden."
        Exit 1
    }
    Write-Host "✅ Python erfolgreich installiert."
} else {
    Write-Host "✅ Python gefunden."
}

# Starte den Haupt-Installationsprozess
Write-Host "[INFO] Starte Installationsprozess für SystemManager-SageHelper..."
python $PSScriptRoot/../src/visual_installer.py

Write-Host "✅ Installationsprozess abgeschlossen. Sie können das Programm jetzt verwenden."