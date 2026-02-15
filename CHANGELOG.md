# Changelog

## [Unreleased]
### Hinzugefügt
- One-Click-Windows-Installer (`Install-SystemManager-SageHelper.cmd` + `scripts/install_assistant.ps1`) für ZIP-basierte Server-Installation.
- Neues Installations-Kernmodul mit automatischer Prüfung/Installation von Git und Python unter Windows.
- Unit-Tests für den Installationskern.
- Installer-Logging für CMD/PowerShell/Python ergänzt, damit Fehlerberichte reproduzierbar geteilt werden können.
- `Install-SystemManager-SageHelper.cmd` pausiert jetzt nach Abschluss, damit Fehlermeldungen nicht sofort verschwinden.
- Windows-Launcher schreibt nun immer ein eigenes Log (`logs/install_launcher.log`) und verwendet explizit `powershell.exe`, damit Startfehler aus ZIP-Installationen nachvollziehbar bleiben.
- Windows-Launcher erkennt Doppelklick-Starts (`cmd /c`) und startet sich in einem persistierenden CMD-Fenster neu, damit die Ausgabe nicht sofort verschwindet.

## [0.1.0] - 2026-02-15
### Hinzugefügt
- Projektgrundgerüst mit modularer Python-Architektur.
- AGENTS.md mit verbindlichen Entwicklungsregeln.
- CLI-Prototyp für Server-Analyse, Strukturprüfung und Markdown-Export.
- Installationsassistent und erste Unit-Tests.
