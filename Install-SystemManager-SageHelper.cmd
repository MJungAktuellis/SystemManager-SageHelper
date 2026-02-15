@echo off
setlocal
REM Starter fuer Windows: startet den PowerShell-Installer aus dem Projektordner.

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%scripts\install_assistant.ps1"

if not exist "%PS_SCRIPT%" (
    echo [FEHLER] Installationsskript nicht gefunden: %PS_SCRIPT%
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
exit /b %errorlevel%
