# SystemManager-SageHelper

SystemManager-SageHelper ist ein Python-Werkzeug für Consulting- und Support-Teams, die Windows-Server im Sage100-Umfeld standardisiert analysieren, prüfen und dokumentieren möchten.

## Aktueller Stand (MVP)

- **Server-Scan (Basis):** Prüft definierte TCP-Ports und erfasst Grundinformationen.
- **Ordner-Check:** Prüft, ob die gewünschte `SystemAG`-Ordnerstruktur vorhanden ist.
- **Markdown-Export:** Erstellt eine direkt nutzbare Dokumentation für Microsoft Loop.
- **Installationsassistent:** Unterstützt den einfachen Einstieg.

## Projektstruktur

```text
SystemManager-SageHelper/
├── AGENTS.md
├── CHANGELOG.md
├── Install-SystemManager-SageHelper.cmd
├── README.md
├── requirements.txt
├── logs/
│   └── assistant_log.md
├── scripts/
│   ├── install.py
│   └── install_assistant.ps1
├── src/
│   └── systemmanager_sagehelper/
│       ├── __init__.py
│       ├── __main__.py
│       ├── analyzer.py
│       ├── cli.py
│       ├── config.py
│       ├── folder_structure.py
│       ├── installer.py
│       ├── models.py
│       └── report.py
└── tests/
    ├── test_folder_structure.py
    ├── test_installer.py
    └── test_report.py
```

## Technische Architektur

### Single Source of Truth

- **Paketpfad `src/systemmanager_sagehelper/` ist führend** für alle Fachmodule (Analyse, Freigaben, Doku, Workflow).
- Legacy-Dateien unter `src/*.py` dienen nur noch als **kompatible Wrapper** für bestehende Aufrufe.
- Gemeinsame Zielserver-Logik (Parsing, Normalisierung, Rollenabbildung) ist zentral in `targeting.py` umgesetzt und wird von CLI und GUI identisch genutzt.

### Module und Datenfluss

1. **Installation (`installer.py`)**
   - prüft Werkzeuge (Git/Python/Pip) und liefert strukturierte Statusobjekte.
2. **Analyse (`analyzer.py`)**
   - verarbeitet `ServerZiel`-Objekte,
   - führt Discovery/Portprüfung aus,
   - ergänzt Rollenableitung (SQL/APP/CTX) über Ports, Dienste und Software.
3. **Ordner/Freigaben (`share_manager.py`, `folder_structure.py`)**
   - stellt Zielstruktur her,
   - setzt SMB-Freigaben mit robustem Fallback bei lokalisierungsbedingten Principal-Problemen.
4. **Dokumentation (`report.py`, `documentation.py`)**
   - erzeugt Analyse-Report (Markdown) plus konsolidierte Log-Dokumentation.
5. **Orchestrierung (`workflow.py`)**
   - steuert den Standardablauf: **Installation → Analyse → Ordner/Freigaben → Dokumentation**,
   - nutzt ein einheitliches Fortschrittsmodell (`WorkflowSchritt`, Prozentwert, Meldung),
   - liefert pro Schritt ein standardisiertes Ergebnisobjekt (`SchrittErgebnis`).

### Erweiterungspunkte für Drittentwickler

- **Remote-Inventar erweitern:** neue Adapter über `RemoteDatenProvider` in `analyzer.py` anbinden (z. B. produktives WinRM/WMI).
- **Workflow erweitern:** zusätzliche Schritte in `workflow.py` ergänzen, ohne bestehende CLI/GUI-Verbraucher zu brechen.
- **Eigene Ausgaben:** zusätzliche Reporter (JSON/HTML) auf Basis von `AnalyseErgebnis` erstellen und in Schritt „Dokumentation“ integrieren.

## Installation

## Schnellstart für Einsteiger ("Dummies")

Wenn du das Tool **einfach nur installieren und benutzen** willst, gehe genau so vor:

1. **ZIP herunterladen und entpacken**
   - Lege den Ordner z. B. auf dem Desktop ab.
2. **Installer starten**
   - Öffne den entpackten Ordner.
   - Starte `Install-SystemManager-SageHelper.cmd` mit Doppelklick (Standard: GUI-Installer).
3. **Rückfragen bestätigen**
   - Windows kann nach Admin-Rechten fragen (UAC) → mit **Ja** bestätigen.
4. **Warten, bis "Fertig" erscheint**
   - Das Fenster nicht schließen, bis der Assistent abgeschlossen ist.
5. **Programm starten**
   - Über die angelegte Startmenü-Verknüpfung oder erneut über den Projektordner.

### Erste Bedienung in 3 Schritten

1. **Server eintragen** (z. B. `srv-app-01` oder IP-Adresse).
2. **Analyse starten**.
3. **Bericht öffnen** unter `docs/` (Markdown-Datei für Doku / Microsoft Loop).

### Wenn etwas nicht funktioniert

Bitte für Supportfälle **nur den kanonischen Installer-Flow** verwenden:

1. `Install-SystemManager-SageHelper.cmd`
2. `scripts/install_assistant.ps1`
3. `scripts/install.py` (Orchestrierung GUI/CLI)
4. `src/systemmanager_sagehelper/installer.py` (Kernlogik)

Teile bei Supportanfragen immer diese reproduzierbaren Artefakte aus `logs/`:
- `logs/install_launcher.log` (CMD-Launcher)
- `logs/install_assistant_ps.log` (PowerShell-Launcher)
- `logs/install_engine.log` (Installer-Engine)
- `logs/install_report.md` (Installationsreport)

> Tipp für Teams: Beim ersten Rollout einmal mit einem Testserver prüfen, dann den gleichen Ablauf für alle weiteren Server nutzen.

### Option A: GUI-Installer unter Windows (Standard, empfohlen)

1. Repository als ZIP auf den Zielserver kopieren und entpacken.
2. `Install-SystemManager-SageHelper.cmd` per Doppelklick ausführen.
3. Der Launcher startet die kanonische Python-Orchestrierung (`scripts/install.py --mode auto`).
4. Im Modus `auto` wird zuerst GUI versucht und bei Fehlern automatisch auf CLI zurückgefallen.
5. Im One-Click-/GUI-Flow ist die Option **Desktop-Verknüpfung** standardmäßig aktiviert und wird im Abschluss inkl. Status ausgewiesen.
6. Standardmäßig schließt sich das Fenster nach erfolgreicher Installation automatisch (keine unnötig offene Konsole).
7. Bei Fehlern bitte die Dateien `logs/install_launcher.log`, `logs/install_assistant_ps.log`, `logs/install_engine.log` und `logs/install_report.md` teilen.

#### CMD-Launcher: Konsole/Debug steuern

Der Launcher `Install-SystemManager-SageHelper.cmd` unterstützt folgende Schalter:

- `--persist-console`: Öffnet den Installer in einer persistenten `cmd /k`-Konsole (Support-/Debug-Modus).
- `--pause`: Erzwingt ein `pause` am Ende, auch bei erfolgreichem Lauf.
- `--nopause`: Unterdrückt das `pause` (außer wenn `--pause` explizit gesetzt ist).

Standardlogik ohne Schalter:

- **Erfolg (`Exit-Code 0`)**: Konsole schließt automatisch.
- **Fehler (`Exit-Code != 0`)**: Konsole pausiert, damit Fehlermeldungen sichtbar bleiben.

Beispiel für Supportfälle:

```cmd
Install-SystemManager-SageHelper.cmd --persist-console --pause
```

### Option B: CLI-Installation (optional, plattformübergreifend)

Interaktiver CLI-Modus:

```bash
python scripts/install.py --mode cli
```

Non-Interactive CLI-Modus (z. B. für Automatisierung):

```bash
python scripts/install.py --mode cli --non-interactive
```

Desktop-Verknüpfung im CLI-Installer:

- Standardmäßig **aktiv** (entspricht One-Click-Verhalten).
- Explizit aktivieren: `--desktop-icon`
- Explizit deaktivieren: `--no-desktop-icon`

Beispiele:

```bash
python scripts/install.py --mode cli --non-interactive --desktop-icon
python scripts/install.py --mode cli --non-interactive --no-desktop-icon
```

## Windows-Build & distributierbares Installer-Paket

Für Enterprise-Umgebungen ist ein reproduzierbarer Windows-Buildpfad enthalten:

1. **App-Binary bauen**: PyInstaller erzeugt eine GUI-Executable aus `src/gui_manager.py`.
2. **Installer bauen**: Inno Setup erstellt ein signierbares Setup-Paket mit sauberem Uninstall-Eintrag.

### Voraussetzungen

- Windows Build-Host mit Python 3.11+
- Inno Setup 6.x (`iscc` im `PATH`)

### Reproduzierbarer Build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1 -Version 1.0.0 -Publisher "SystemManager Team"
```

Das Skript erzeugt anschließend:

- Binary: `build/dist/SystemManager-SageHelper.exe`
- Setup-Paket: `build/installer/SystemManager-SageHelper-<Version>-setup.exe`

### Installationsziele des Setups

- **Programmdateien (nur lesen/ausführen):** `%ProgramFiles%\SystemManager-SageHelper`
- **Schreibbare Laufzeitdaten:** `%ProgramData%\SystemManager-SageHelper`
  - `%ProgramData%\SystemManager-SageHelper\config`
  - `%ProgramData%\SystemManager-SageHelper\logs`

Der Installer setzt die Ordnerrechte unter `%ProgramData%` so, dass Standardbenutzer Konfigurationen und Logs schreiben können.

### Registrierung in „Programme und Features“

Der Installer registriert automatisch einen vollständigen Deinstallations-Eintrag mit:

- `DisplayName`: `SystemManager-SageHelper`
- `DisplayVersion`: über `-Version` im Buildskript
- `Publisher`: über `-Publisher` im Buildskript
- `UninstallString`: vom Installer automatisch gepflegt

### Verknüpfungen

- Startmenü-Verknüpfung auf den GUI-Launcher wird standardmäßig erstellt.
- Optionale Desktop-Verknüpfung ist im Setup als auswählbare Aufgabe verfügbar.

### Deinstallation

Es gibt zwei saubere Wege:

1. **Windows GUI:** „Programme und Features“ → `SystemManager-SageHelper` → Deinstallieren.
2. **Direkt über Uninstaller:** `C:\Program Files\SystemManager-SageHelper\unins*.exe`

> Hinweis: Nutzdaten in `%ProgramData%\SystemManager-SageHelper` können für Audits bewusst erhalten bleiben und bei Bedarf manuell gelöscht werden.

### Troubleshooting (Adminrechte / UAC)

- **Setup fordert Adminrechte an:** Das ist korrekt, weil nach `%ProgramFiles%` installiert wird.
- **UAC-Dialog erscheint nicht:** Setup explizit per Rechtsklick „Als Administrator ausführen“ starten.
- **`iscc` nicht gefunden:** Inno Setup installieren und den Compiler-Pfad in die `PATH`-Variable aufnehmen.
- **`PyInstaller`-Build bricht ab:** Buildskript erneut mit `-Clean` ausführen, damit alte Artefakte entfernt werden.

## Verwendung

### 1) Multi-Server-Scan und Markdown-Export

```bash
PYTHONPATH=src python -m systemmanager_sagehelper scan \
  --server srv-app-01,srv-sql-01 \
  --rollen APP \
  --deklaration 'srv-app-01=APP;srv-sql-01=SQL' \
  --out docs/serverbericht.md
```

### 2) Server im Subnetz automatisch finden und analysieren

```bash
PYTHONPATH=src python -m systemmanager_sagehelper scan \
  --discover-base 192.168.10 \
  --discover-start 1 \
  --discover-end 50 \
  --rollen APP,SQL,CTX \
  --out docs/serverbericht-auto.md
```

### 3) Ordnerstruktur prüfen

```bash
PYTHONPATH=src python -m systemmanager_sagehelper ordner-check --basis /tmp/SystemAG
```

### 4) Fehlende Ordner direkt anlegen

```bash
PYTHONPATH=src python -m systemmanager_sagehelper ordner-check --basis /tmp/SystemAG --anlegen
```

### 5) Dokumentationsmodus für Microsoft Loop (kompakt)

Der Workflow erzeugt die `docs/ServerDokumentation.md` standardmäßig im **Modus `loop`**:

- entscheidungsorientiert (Executive Summary + priorisierte Maßnahmen),
- konsistente Artefaktverweise (`Analysebericht`, `Logpfade`, `Lauf-IDs`),
- Rohlogs nur als **Anhang/Referenz**.

Beispielauszug:

```md
## Kopfbereich
- Kunde: nicht angegeben
- Umgebung: nicht angegeben
- Lauf-ID: lauf-20260102-110000-efgh5678
- Berichtsmodus: Loop (kompakt)

## Maßnahmen/Offene Punkte
| Priorität | Maßnahme |
| --- | --- |
| P1 | srv-sql-01: Port 1433 (MSSQL) prüfen/freischalten |
```

Für technische Tiefenanalysen kann `erstelle_dokumentation(..., berichtsmodus="voll")` verwendet werden.


## Logging, Berichte und Lauf-ID-Korrelation

- **Zentrales Analyse-Log:** `logs/server_analysis.log`
- **GUI-Log:** `logs/server_analysis_gui.log`
- **CLI-Log:** `logs/cli.log`
- **Ordnerverwaltung:** `logs/folder_manager.log`
- **Dokumentationslauf:** `logs/doc_generator.log`
- **Ergebnisbericht (CLI):** über `--out`, z. B. `docs/serverbericht.md`
- **Ergebnisbericht (Dokumentationsmodul):** `docs/ServerDokumentation.md`

Alle Logs verwenden ein einheitliches Format mit `run_id=...`. Diese Lauf-ID wird auch im Markdown-Bericht ausgegeben.
So kann ein Analyse-Lauf eindeutig korreliert werden:

1. Lauf-ID im Bericht ablesen (`- Lauf-ID: ...`).
2. In den Logdateien nach derselben ID suchen (`run_id=<lauf-id>`).
3. Damit alle zugehörigen Einträge aus Analyse, GUI und CLI zusammenführen.

Das Modul `src/doc_generator.py` liest standardmäßig `*.log` und optional Legacy-Dateien `*.txt`, damit bestehende Umgebungen ohne harte Migration weiter funktionieren.

## Nächste sinnvolle Erweiterungen

1. WinRM-/PowerShell-Remoting für echte Remote-Systeminfos (OS, Dienste, Treiber, Freigaben).
2. Rollenabhängige Prüfprofile (APP, SQL, CTX) mit separaten Regeln.
3. Prüfmodul für Freigaben und Berechtigungen (`SystemAG$`, `AddinsOL$`, `LiveupdateOL$`).
4. Geführte Oberfläche (CLI-Wizard oder Web-UI) für nicht-technische Nutzer.

## Qualitätsziele

- Deutsche Kommentare und Dokumentation.
- Klare Modultrennung für einfache Erweiterbarkeit.
- Tests für Kernlogik.
- Reproduzierbarer Ablauf über AGENTS.md und CI-fähige Struktur.
