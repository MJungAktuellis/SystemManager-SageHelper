<#
.SYNOPSIS
  Reproduzierbarer Build für ein distributierbares Windows-Installer-Paket.

.DESCRIPTION
  1) Erstellt eine PyInstaller-Binary auf Basis von src/gui_manager.py.
  2) Staged Programmdateien unter build/staging.
  3) Baut mit Inno Setup ein Setup-Paket inkl. Uninstall-Eintrag,
     Startmenü-Verknüpfung und optionalem Desktop-Shortcut.
#>

[CmdletBinding()]
param(
    [string]$Version = "0.1.0",
    [string]$Publisher = "SystemManager Team",
    [string]$EntryPoint = "src/gui_manager.py",
    [string]$AppName = "SystemManager-SageHelper",
    [string]$PythonExe = "python",
    [string]$InnoCompiler = "iscc",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Resolve-RepoRoot {
    # Skript liegt in scripts/, deshalb ist der Parent-Parent das Repository-Root.
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Assert-Tooling {
    param(
        [string]$Python,
        [string]$Inno
    )

    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
        throw "Python-Interpreter '$Python' wurde nicht gefunden."
    }
    if (-not (Get-Command $Inno -ErrorAction SilentlyContinue)) {
        throw "Inno-Setup-Compiler '$Inno' wurde nicht gefunden (iscc)."
    }
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $joinedArgs = $Arguments -join " "
    Write-Host "[RUN] $FilePath $joinedArgs"

    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Befehl fehlgeschlagen (ExitCode=$($process.ExitCode)): $FilePath $joinedArgs"
    }
}

$repoRoot = Resolve-RepoRoot
$buildRoot = Join-Path $repoRoot "build"
$distRoot = Join-Path $buildRoot "dist"
$workRoot = Join-Path $buildRoot "pyinstaller"
$specRoot = Join-Path $buildRoot "spec"
$stagingRoot = Join-Path $buildRoot "staging"
$installerScript = Join-Path $repoRoot "installer/SystemManager-SageHelper.iss"
$entryPointPath = Join-Path $repoRoot $EntryPoint
$binaryName = "$AppName.exe"

Write-Step "Prüfe Tooling"
Assert-Tooling -Python $PythonExe -Inno $InnoCompiler

if (-not (Test-Path $entryPointPath)) {
    throw "Entry-Point nicht gefunden: $entryPointPath"
}
if (-not (Test-Path $installerScript)) {
    throw "Inno-Setup-Skript nicht gefunden: $installerScript"
}

if ($Clean -and (Test-Path $buildRoot)) {
    Write-Step "Bereinige vorhandene Build-Artefakte"
    Remove-Item -Recurse -Force $buildRoot
}

New-Item -ItemType Directory -Force -Path $distRoot, $workRoot, $specRoot, $stagingRoot | Out-Null

Write-Step "Installiere/aktualisiere Build-Abhängigkeiten"
Invoke-Checked -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pip", "pyinstaller") -WorkingDirectory $repoRoot

Write-Step "Erzeuge GUI-Binary mit PyInstaller"
Invoke-Checked -FilePath $PythonExe -WorkingDirectory $repoRoot -Arguments @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onefile",
    "--name", $AppName,
    "--distpath", $distRoot,
    "--workpath", $workRoot,
    "--specpath", $specRoot,
    "--paths", "src",
    $entryPointPath
)

$binaryPath = Join-Path $distRoot $binaryName
if (-not (Test-Path $binaryPath)) {
    throw "PyInstaller-Binary wurde nicht erzeugt: $binaryPath"
}

Write-Step "Stage Programmdateien für Installer"
Copy-Item -Path $binaryPath -Destination (Join-Path $stagingRoot $binaryName) -Force
if (Test-Path (Join-Path $repoRoot "README.md")) {
    Copy-Item -Path (Join-Path $repoRoot "README.md") -Destination (Join-Path $stagingRoot "README.md") -Force
}
if (Test-Path (Join-Path $repoRoot "CHANGELOG.md")) {
    Copy-Item -Path (Join-Path $repoRoot "CHANGELOG.md") -Destination (Join-Path $stagingRoot "CHANGELOG.md") -Force
}

Write-Step "Baue Setup.exe mit Inno Setup"
Invoke-Checked -FilePath $InnoCompiler -WorkingDirectory $repoRoot -Arguments @(
    "/Qp",
    "/DMyAppVersion=$Version",
    "/DMyAppPublisher=$Publisher",
    "/DMyAppExeName=$binaryName",
    "/DMyBuildRoot=$buildRoot",
    $installerScript
)

Write-Step "Build abgeschlossen"
Write-Host "Binary:   $binaryPath"
Write-Host "Installer: $(Join-Path $buildRoot "installer")"
