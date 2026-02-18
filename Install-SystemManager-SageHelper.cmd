@echo off
setlocal
REM Starter fuer Windows: startet den PowerShell-Installer aus dem Projektordner.
REM Standardverhalten: Fenster schliesst nach erfolgreichem Lauf automatisch.
REM Debug-Hilfen: --persist-console (Konsole offen halten), --pause (am Ende pausieren).

set "SCRIPT_PATH=%~f0"
set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%scripts\install_assistant.ps1"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "LAUNCHER_LOG=%LOG_DIR%\install_launcher.log"

set "INTERNAL_PERSIST=0"
set "PERSIST_CONSOLE=0"
set "FORCE_PAUSE=0"
set "NO_PAUSE=0"

REM Parameter robust einlesen, damit Reihenfolge der Schalter flexibel bleibt.
:parse_args
if "%~1"=="" goto after_parse
if /I "%~1"=="--internal-persist" (
    set "INTERNAL_PERSIST=1"
    shift
    goto parse_args
)
if /I "%~1"=="--persist-console" (
    set "PERSIST_CONSOLE=1"
    shift
    goto parse_args
)
if /I "%~1"=="--pause" (
    set "FORCE_PAUSE=1"
    shift
    goto parse_args
)
if /I "%~1"=="--nopause" (
    set "NO_PAUSE=1"
    shift
    goto parse_args
)
echo [WARN] Unbekannter Parameter wird ignoriert: %~1
shift
goto parse_args

:after_parse

REM Optionales persistentes CMD-Fenster nur auf ausdruecklichen Wunsch aktivieren.
REM Die /c-Erkennung verhindert Rekursion, wenn bereits in einer dauerhaften Konsole gestartet.
if "%INTERNAL_PERSIST%"=="0" if "%PERSIST_CONSOLE%"=="1" (
    echo %CMDCMDLINE% | findstr /I /C:"/c" >nul
    if not errorlevel 1 (
        REM In CMD werden Anfuehrungszeichen mit doppelten Quotes maskiert, nicht mit Backslashes.
        start "SystemManager-SageHelper Installer" cmd /k ""%SCRIPT_PATH%" --internal-persist --pause"
        exit /b 0
    )
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ===== [%date% %time%] Start Install-SystemManager-SageHelper.cmd =====>>"%LAUNCHER_LOG%"

if not exist "%PS_SCRIPT%" (
    echo [FEHLER] Installationsskript nicht gefunden: %PS_SCRIPT%
    echo [FEHLER] Installationsskript nicht gefunden: %PS_SCRIPT%>>"%LAUNCHER_LOG%"
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo === Starte kanonischen Installer-Flow ===
echo [INFO] Launcher-Log: %LAUNCHER_LOG%
echo [INFO] Flow: scripts\install_assistant.ps1 -> scripts\install.py -> systemmanager_sagehelper.installer
echo [INFO] Optional: CLI direkt via "python scripts\install.py --mode cli"
echo [INFO] Optional: Non-Interactive via "python scripts\install.py --non-interactive"
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
    echo logs\install_assistant_ps.log und logs\install_engine.log.
)

set "SHOULD_PAUSE=0"
if not "%EXIT_CODE%"=="0" set "SHOULD_PAUSE=1"
if "%FORCE_PAUSE%"=="1" set "SHOULD_PAUSE=1"
if "%NO_PAUSE%"=="1" if "%FORCE_PAUSE%"=="0" set "SHOULD_PAUSE=0"

if "%SHOULD_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
