# Deinstallationsassistent für SystemManager-SageHelper.
# Ziel: Sauberes Entfernen der Anwendung inkl. optionaler Restdaten.
[CmdletBinding(SupportsShouldProcess = $true)]
Param(
    [string]$InstallPath = "C:\Program Files\SystemManager-SageHelper",
    [switch]$PurgeUserData,
    [switch]$Quiet
)

function Write-Status {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet("INFO", "WARN", "FEHLER", "OK")][string]$Level = "INFO"
    )

    $prefix = "[$Level]"
    Write-Host "$prefix $Message"
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-DesktopShortcut {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "SystemManager-SageHelper.lnk"
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction Stop
        Write-Status -Level "OK" -Message "Desktop-Verknüpfung entfernt: $shortcutPath"
    }
}

function Remove-InstallationDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Status -Level "WARN" -Message "Installationspfad nicht gefunden: $Path"
        return
    }

    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
    Write-Status -Level "OK" -Message "Installationsverzeichnis entfernt: $Path"
}

function Remove-UserData {
    $targets = @(
        (Join-Path $env:LOCALAPPDATA "SystemManager-SageHelper"),
        (Join-Path $env:APPDATA "SystemManager-SageHelper")
    )

    foreach ($target in $targets) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
            Write-Status -Level "OK" -Message "Benutzerdaten entfernt: $target"
        }
    }
}

try {
    if (-not (Test-Administrator)) {
        throw "Bitte die Deinstallation mit Administratorrechten starten."
    }

    if (-not $Quiet) {
        Write-Host "=== SystemManager-SageHelper Deinstallation ==="
        Write-Status -Level "INFO" -Message "Installationspfad: $InstallPath"
        if ($PurgeUserData) {
            Write-Status -Level "INFO" -Message "Option aktiviert: Benutzerdaten werden mit entfernt."
        }
    }

    if ($PSCmdlet.ShouldProcess($InstallPath, "SystemManager-SageHelper entfernen")) {
        Remove-DesktopShortcut
        Remove-InstallationDirectory -Path $InstallPath
        if ($PurgeUserData) {
            Remove-UserData
        }
    }

    Write-Status -Level "OK" -Message "Deinstallation erfolgreich abgeschlossen."
    exit 0
}
catch {
    Write-Status -Level "FEHLER" -Message "Deinstallation fehlgeschlagen: $($_.Exception.Message)"
    exit 1
}
