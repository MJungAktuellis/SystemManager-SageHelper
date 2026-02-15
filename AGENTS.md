# AGENTS.md

## Projektname: SystemManager-SageHelper

### 🌟 **Projektziel**
Ein benutzerfreundliches und einfach zu installierendes Tool, das Serveranalysen und -konfigurationen für Microsoft Windows-Server vereinfacht. Ziel ist es, IT-Administratoren und Support-Dienstleistern (insbesondere im Zusammenhang mit Sage100 und anderen Zusatztools) die Arbeit zu erleichtern, indem manuelle, wiederkehrende Aufgaben automatisiert werden. Dazu gehören insbesondere:

- **Automatische Serveranalyse**: Erkennung von Serverrollen (SQL, App, CTX etc.), installierten Treibern und relevanten Ports, die für den korrekten Betrieb von Software wie Sage100 benötigt werden.
- **Automatische Ordnerstrukturen**: Anlegen und Prüfen von vordefinierten Ordnerstrukturen inkl. Berechtigungsmanagement.
- **Dokumentation**: Automatische Erstellung von Berichten und Markdown-Dokumentationen, um Änderungen und Analysen zu protokollieren und in Unternehmenslösungen wie Microsoft Loop einzubinden.

---

### ✨ **Funktionen**
1. **Server-Analyse**:
   - Erkennung der Serverrolle (SQL-Server, Anwendungsserver (APP), Terminalserver (CTX)).
   - Überprüfung installierter Treiberversionen und Segmentprüfung (Windows Firewall, Portstatus).
   - Generierung von Berichten über gefundene Software und Einstellungen.

2. **Ordnermanagement und Berechtigungen:**
   - Erstellung einer vordefinierten Ordnerstruktur auf Zielservern.
   - Prüfung auf vorhandene Ordnerstruktur mit Option, diese zu ergänzen oder eine Kopie zu erstellen.
   - Automatische Vergabe von Freigabeberechtigungen (inkl. $-Freigaben).

3. **Interaktive Benutzeroberfläche:**
   - XAML-basierte GUI für eine intuitive Bedienung.
   - Benutzer kann Server manuell hinzufügen, ein Netzwerk scannen oder relevante Einstellungen in der GUI vornehmen.

4. **Automatische Markdown-Dokumentation:**
   - Zusammenstellung von Änderungen und Analysen in Markdown-Dateien zur Einbindung in Microsoft Loop.
   - Strukturierte Berichte in spezifische Verzeichnisse speichern.

5. **Installationsassistent:**
   - Automatisiertes Installationsskript für die einfache Einrichtung, inklusive Überprüfung und Installation von Python.
   - Installation und Konfiguration aller Komponenten in einem standardisierten Verzeichnis (z. B. `C:\Program Files\SystemManager-SageHelper`).

---

### 💻 **Technische Anforderungen**
1. **Laufzeitumgebung:**
   - Microsoft Windows Server (verschiedene Versionen, inkl. 2012, 2016, 2019).
   - Python 3.11 oder höher.

2. **Sprach- und Technologieauswahl:**
   - **Python** für serverseitige Prozesse, Analyse und Datenverarbeitung.
   - **PowerShell** für systemnahe Aufgaben und GUI-Integration.

3. **Repository-Aufbau:**
   ```
   SystemManager-SageHelper/
   ├── src/                    # Hauptverzeichnis für Python-Skripte
   │   ├── server_analysis.py  # Analyse von Serverrollen und Komponenten
   │   ├── folder_manager.py   # Verwaltung der Ordnerstruktur
   │   └── doc_generator.py    # Automatische Generierung von Dokumentation
   ├── scripts/                # Skripte für Installation und Start
   │   └── install_assistant.ps1
   ├── tests/                  # Unit-Tests für alle Module
   ├── docs/                   # Projektdokumentation & Benutzerhilfe
   ├── logs/                   # Logs des Programms
   ├── requirements.txt        # Python-Abhängigkeiten
   ├── README.md
   ├── AGENTS.md               # Projektübersicht und Zielsetzung
   └── CHANGELOG.md
   ```

4. **Themesicherheit und Logs:**
   - Jeder Schritt wird zentral geloggt.
   - Protokollierung aller Änderungen auf dem Zielsystem zur Nachvollziehbarkeit.

---
### 🔄 **Handlungsplan**
1. **Implementierung einer standardisierten auf Python basierten Lösungsarchitektur**.
2. Schreiben von Python-Funktionen:
   - Servererkennung und Datenextraktion.
   - Überprüfung der Konfiguration (Ports, Treiberversionen).
   - Erstellung von Ordnerstrukturen mit angepassten Freigaben.
3. Bereitstellung sämtlicher Logs und Markdown-Dokumentationen für eine nahtlose Einbindung in Microsoft Loop.

4. **Entwicklung eines Installationsassistenten:**
   - Automatische Installation aller Abhängigkeiten.
   - Einfache Benutzerführung.

---

### 📄 **Weitere Vorschläge für Funktionen**
- Verwendung eines Zentral-Dashboards zur Anzeige der Analyseergebnisse.
- Erweiterbarkeit durch API oder Plugins für zukünftige Anforderungen.

---

Lass mich wissen, ob ich direkt mit der Umsetzung der Module aus der Übersicht starten soll.