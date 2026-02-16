@echo off
setlocal
REM Starter fuer Windows: startet den PowerShell-Installer aus dem Projektordner.
REM Mit --nopause kann das Pausieren am Ende deaktiviert werden.
REM Falls per Doppelklick gestartet, wird einmalig ein persistentes CMD-Fenster geoeffnet.

set "SCRIPT_PATH=%~f0"
set "CONSOLE_MARKER=%~1"

if /I not "%CONSOLE_MARKER%"=="--persist-console" (
    echo %CMDCMDLINE% | findstr /I /C:"/c" >nul
    if not errorlevel 1 (
        REM WICHTIG: In CMD werden Anfuehrungszeichen mit doppelten Quotes maskiert,
        REM nicht mit Backslashes. Sonst versucht cmd ein Literal wie '\"C:\...\"'
        REM auszufuehren und meldet "is not recognized as an internal or external command".
        start "SystemManager-SageHelper Installer" cmd /k ""%SCRIPT_PATH%" --persist-console"
        exit /b 0
    )
)

if /I "%CONSOLE_MARKER%"=="--persist-console" shift

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%scripts\install_assistant.ps1"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "LAUNCHER_LOG=%LOG_DIR%\install_launcher.log"
set "NO_PAUSE=0"

if /I "%~1"=="--nopause" set "NO_PAUSE=1"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ===== [%date% %time%] Start Install-SystemManager-SageHelper.cmd =====>>"%LAUNCHER_LOG%"

if not exist "%PS_SCRIPT%" (
    echo [FEHLER] Installationsskript nicht gefunden: %PS_SCRIPT%
    echo [FEHLER] Installationsskript nicht gefunden: %PS_SCRIPT%>>"%LAUNCHER_LOG%"
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo === Starte One-Click-Installer ===
echo [INFO] Launcher-Log: %LAUNCHER_LOG%
echo [INFO] Nutze PowerShell-Skript: %PS_SCRIPT%

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" >>"%LAUNCHER_LOG%" 2>&1
set "EXIT_CODE=%errorlevel%"

echo [INFO] Exit-Code: %EXIT_CODE%>>"%LAUNCHER_LOG%"
echo ===== [%date% %time%] Ende Install-SystemManager-SageHelper.cmd =====>>"%LAUNCHER_LOG%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Installation beendet.
) else (
    echo [FEHLER] Installation beendet mit Exit-Code %EXIT_CODE%.
    echo Bitte pruefen Sie die Logdateien unter logs\install_launcher.log,
    echo logs\install_assistant_ps.log und logs\install_assistant.log.
)

if "%NO_PAUSE%"=="0" pause
exit /b %EXIT_CODE%
