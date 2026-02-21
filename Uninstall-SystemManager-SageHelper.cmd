@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "UNINSTALL_PS=%SCRIPT_DIR%scripts\uninstall_assistant.ps1"

if not exist "%UNINSTALL_PS%" (
    echo [FEHLER] Deinstallationsskript nicht gefunden: %UNINSTALL_PS%
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UNINSTALL_PS%"
set "EXIT_CODE=%errorlevel%"

if "%EXIT_CODE%"=="0" (
    echo [OK] Deinstallation abgeschlossen.
) else (
    echo [FEHLER] Deinstallation fehlgeschlagen (Exit-Code %EXIT_CODE%).
)

pause
exit /b %EXIT_CODE%
