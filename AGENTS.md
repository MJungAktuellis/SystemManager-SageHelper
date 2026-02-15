# AGENTS.md

Diese Datei definiert verbindliche Arbeitsregeln für dieses Repository.

## Ziel des Projekts
SystemManager-SageHelper unterstützt Consulting-/Support-Teams bei der technischen Erfassung, Prüfung und Dokumentation von Windows-Servern im Sage100-Umfeld.

## Coding-Standards
- Kommentare, Docstrings und Nutzertexte sind auf **Deutsch** zu verfassen.
- Python-Code folgt modernen Best Practices (PEP8, klare Modularisierung, hohe Lesbarkeit).
- Keine hartkodierten absoluten Pfade; stattdessen `pathlib.Path` verwenden.
- Bezeichner sollen eindeutig und fachlich verständlich sein.
- Komplexe Logikabschnitte müssen kurz erklärt werden.

## Architektur-Regeln
- Geschäftslogik in `src/systemmanager_sagehelper/` kapseln.
- Ein-/Ausgabe (CLI, Dateisystem) von Kernlogik trennen.
- Datenstrukturen bevorzugt als `dataclass` modellieren.
- Dokumentations-Export (Markdown für Microsoft Loop) als eigene Komponente behandeln.

## Qualitätssicherung
- Für neue Kernfunktionen Unit-Tests in `tests/` ergänzen.
- Vor Commit mindestens `python -m unittest` ausführen.
- README und CHANGELOG bei relevanten Änderungen aktualisieren.

## Git-Konvention
- Commit-Nachrichten im Stil: `<typ>: <deutsche Kurzbeschreibung>`
- Erlaubte Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Erweiterungshinweise
- Neue Serverrollen als eigenständige Prüfmodule ergänzen.
- Port-/Treiberanforderungen zentral in der Konfiguration pflegen.
- Für produktiven Remote-Zugriff (WinRM/PowerShell Remoting) Adapter-Klasse erweitern.
