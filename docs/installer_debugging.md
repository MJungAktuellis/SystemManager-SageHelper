# CMD-/PowerShell-Installer Debugging (SystemManager-SageHelper)

## Schnellstart

```cmd
Install-SystemManager-SageHelper.cmd --debug
```

Optionale Parameter:

- `--offline` aktiviert Offline-Modus (kein Online-Download für Python, `pip --no-index`)
- `--proxy <URL>` übergibt Proxy an `install_assistant.ps1` (für `pip`/Downloads)
- `--no-admin` überspringt die Admin-Prüfung (nur für eingeschränkte Umgebungen/Tests)
- `--pause` hält das Fenster am Ende offen

## Wichtige Logdateien

1. `logs/install_launcher.log` (CMD-Launcher)
2. `logs/install_assistant_ps.log` (PowerShell-Launcher)
3. `logs/install_engine.log` (Python-Installationsengine)

Wenn das Projektverzeichnis nicht beschreibbar ist, wird automatisch auf
`%LOCALAPPDATA%\SystemManager-SageHelper\logs` umgeschaltet.

## Häufige Fehlerbilder

### 1) PowerShell startet nicht
- Symptom: Exit-Code `9009` oder direkte Fehlermeldung im CMD-Launcher
- Reaktion des Launchers: automatischer Python-Direktstart-Fallback
- Maßnahme: PowerShell-Funktionalität prüfen (`where powershell.exe`) und Logs senden

### 2) UAC / Administratorrechte
- Exit-Code `42`: Erhöhung wurde erfolgreich in neues Fenster delegiert
- Exit-Code `1223`: UAC-Abfrage wurde abgebrochen
- Exit-Code `16001`: Erhöhung konnte nicht gestartet werden

### 3) Python wird nicht gefunden
- Reihenfolge: `py -3` → `python` → `python3`
- Bootstrap-Strategien: `winget` → `choco` → lokaler Installer (`scripts/bootstrap` oder `installer/bootstrap`) → optional Online-Download
- Mindestversion: Python `>= 3.8`

### 4) Proxy-/Netzwerkprobleme bei pip
- Installer mit Proxy starten:
  ```cmd
  Install-SystemManager-SageHelper.cmd --proxy http://proxy.firma.local:8080
  ```
- Offline-Installation:
  ```cmd
  Install-SystemManager-SageHelper.cmd --offline
  ```

### 5) Defender/Antivirus blockiert Installationsschritte
- Installer-Verzeichnis als vertrauenswürdig markieren
- Prozesse `powershell.exe`, `python.exe`, `py.exe` temporär zulassen
- Logs auf blockierte Dateioperationen prüfen

## Test-Szenarien (manuell auf Windows)

1. **Standardnutzer + UAC aktiv**
   - Erwartung: UAC-Prompt, zweites Fenster übernimmt, Exit-Code 42 im ersten Fenster
2. **Admin-Konsole direkt**
   - Erwartung: kein UAC-Neustart, direkter Ablauf
3. **Pfad mit Leerzeichen** (z. B. `C:\Temp\Sage Helper Test\`)
   - Erwartung: Skripte laufen ohne Quoting-Fehler
4. **Offline ohne Internet**
   - Erwartung: kein Online-Download, ggf. lokaler Python-Installer oder klarer Abbruchhinweis
5. **Proxy erforderlich**
   - Erwartung: Anforderungen über `--proxy` installierbar
6. **Eingeschränktes Konto (`--no-admin`)**
   - Erwartung: Hinweis im Log, bestmöglicher Ablauf ohne Elevation

## Deinstallation

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_assistant.ps1
```

Mit vollständigem Entfernen von Benutzerdaten:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_assistant.ps1 -PurgeUserData
```
