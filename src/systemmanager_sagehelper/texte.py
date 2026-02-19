"""Zentrale UI- und Berichtstexte für konsistente Lokalisierung.

Dieses Modul bündelt sichtbare Beschriftungen, Statuspräfixe und
Berichtsüberschriften. Dadurch bleiben Formulierungen in der gesamten
Anwendung einheitlich und lassen sich später leicht erweitern.
"""

from __future__ import annotations


# Einheitliche Statuspräfixe für GUI und Berichtsausgaben.
STATUS_PREFIX = "Status:"
STATUS_ERFOLG = "✅ Erfolgreich"
STATUS_WARNUNG = "⚠️ Warnung"
STATUS_HINWEIS = "ℹ️ Info"
STATUS_FEHLER = "❌ Fehler"


# Klar verständliche Statusstufen für den Installationsassistenten.
INSTALLER_STATUS_INFO = "Info"
INSTALLER_STATUS_WARNUNG = "Warnung"
INSTALLER_STATUS_FEHLER = "Fehler"
INSTALLER_STATUS_ERFOLGREICH = "Erfolgreich"


# Wiederverwendbare Schaltflächenbeschriftungen.
BUTTON_SPEICHERN = "Speichern"
BUTTON_ZURUECK = "Zurück"
BUTTON_BEENDEN = "Beenden"
BUTTON_FERTIG = "Fertig"
BUTTON_ANALYSE_STARTEN = "Analyse starten"
BUTTON_NETZWERKERKENNUNG_STARTEN = "Netzwerkerkennung starten"


# Einheitliche Begriffe für UI-Bereiche.
BEGRIFF_ASSISTENT = "Assistent"
BEGRIFF_UEBERSICHT = "Übersicht"
BEGRIFF_NETZWERKERKENNUNG = "Netzwerkerkennung"
BEGRIFF_BERICHT = "Bericht"


# Standardtexte für Berichtsstruktur.
BERICHT_TITEL = "Serverdokumentation"
BERICHT_KOPFBEREICH = "Kopfbereich"
BERICHT_MANAGEMENT_ZUSAMMENFASSUNG = "Management-Zusammenfassung"
BERICHT_SERVERLISTE = "Serverliste"
BERICHT_MASSNAHMEN = "Maßnahmen und offene Punkte"


# Standardtexte rund um den Shell-Meldungsbereich.
SHELL_BEREICH_STATUS_MELDUNGEN = "Status / Meldungen"
SHELL_OPTION_TECHNISCHE_LOGS = "Technische Meldungen anzeigen"
SHELL_STATUS_BEREIT = "Bereit"


# Abschlussseite im Installer-Wizard.
INSTALLER_ABSCHLUSS_WAS_GETAN = "Was wurde getan"
INSTALLER_ABSCHLUSS_NAECHSTE_SCHRITTE = "Was ist als Nächstes zu tun?"
