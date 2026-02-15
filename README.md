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

## Installation

### Option A: One-Click-Installer unter Windows (empfohlen)

1. Repository als ZIP auf den Zielserver kopieren und entpacken.
2. `Install-SystemManager-SageHelper.cmd` per Doppelklick ausführen.
3. Der Assistent installiert bei Bedarf Python/Git und richtet anschließend alle Abhängigkeiten ein.
4. Der Launcher öffnet bei Doppelklick automatisch ein persistentes CMD-Fenster, damit Meldungen nicht sofort verschwinden.
5. Bei Fehlern bitte die Logdateien unter `logs/install_launcher.log`, `logs/install_assistant_ps.log` und `logs/install_assistant.log` teilen.

### Option B: CLI-Installation (plattformübergreifend)

```bash
python scripts/install.py
```

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
