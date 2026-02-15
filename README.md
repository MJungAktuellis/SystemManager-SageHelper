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
├── README.md
├── requirements.txt
├── logs/
│   └── assistant_log.md
├── scripts/
│   └── install.py
├── src/
│   └── systemmanager_sagehelper/
│       ├── __init__.py
│       ├── __main__.py
│       ├── analyzer.py
│       ├── cli.py
│       ├── config.py
│       ├── folder_structure.py
│       ├── models.py
│       └── report.py
└── tests/
    ├── test_folder_structure.py
    └── test_report.py
```

## Installation

```bash
python scripts/install.py
```

## Verwendung

### 1) Server-Scan und Markdown-Export

```bash
PYTHONPATH=src python -m systemmanager_sagehelper scan --server localhost --rollen APP,SQL --out docs/serverbericht.md
```

### 2) Ordnerstruktur prüfen

```bash
PYTHONPATH=src python -m systemmanager_sagehelper ordner-check --basis /tmp/SystemAG
```

### 3) Fehlende Ordner direkt anlegen

```bash
PYTHONPATH=src python -m systemmanager_sagehelper ordner-check --basis /tmp/SystemAG --anlegen
```

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
