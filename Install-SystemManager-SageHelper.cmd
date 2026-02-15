@echo off
setlocal
REM Starter fuer Windows: startet den PowerShell-Installer aus dem Projektordner.
REM Mit --nopause kann das Pausieren am Ende deaktiviert werden.

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%scripts\install_assistant.ps1"
set "NO_PAUSE=0"

if /I "%~1"=="--nopause" set "NO_PAUSE=1"

if not exist "%PS_SCRIPT%" (
    echo [FEHLER] Installationsskript nicht gefunden: %PS_SCRIPT%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo === Starte One-Click-Installer ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Installation beendet.
) else (
    echo [FEHLER] Installation beendet mit Exit-Code %EXIT_CODE%.
    echo Bitte pruefen Sie die Logdatei unter logs\install_assistant.log.
)

if "%NO_PAUSE%"=="0" pause
exit /b %EXIT_CODE%
