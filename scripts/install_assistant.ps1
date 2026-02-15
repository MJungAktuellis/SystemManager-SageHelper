# Installationsassistent – Automatische Python-Installation
Write-Host "=== SystemManager-SageHelper: One-Click-Installer ==="

# Pfad zur Python-Installation prüfen
Write-Host "[INFO] Prüfe, ob Python installiert ist..."
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Python ist nicht installiert. Starte automatische Installation..."

    # Python-Installer herunterladen
    $PythonInstallerUrl = "https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
    $InstallerPath = "$PSScriptRoot\\python-installer.exe"

    Write-Host "[INFO] Lade Python-Installer herunter..."
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $InstallerPath

    # Installer ausführen
    Write-Host "[INFO] Installiere Python..."
    Start-Process -FilePath $InstallerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -NoNewWindow -Wait

    # Überprüfung nach der Installation
    python --version
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Fehler: Python konnte nicht installiert werden."
        Exit 1
    }
    Write-Host "✅ Python erfolgreich installiert."
} else {
    Write-Host "✅ Python gefunden."
}

# Starte die eigentliche Installation
Write-Host "[INFO] Starte Installationsprozess für SystemManager-SageHelper..."
python $PSScriptRoot/../src/visual_installer.py

# Abschließende Meldung
Write-Host "✅ Installationsprozess abgeschlossen. Sie können das Programm jetzt verwenden."