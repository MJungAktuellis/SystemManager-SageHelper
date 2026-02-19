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
STATUS_HINWEIS = "ℹ️ Hinweis"
STATUS_FEHLER = "❌ Fehler"


# Klar verständliche Statusstufen für den Installationsassistenten.
INSTALLER_STATUS_INFO = "Hinweis"
INSTALLER_STATUS_WARNUNG = "Warnung"
INSTALLER_STATUS_FEHLER = "Fehler"
INSTALLER_STATUS_ERFOLGREICH = "Erfolgreich"


# Sprachleitfaden für konsistente Nutzeransprache.
ANREDE_STANDARD = "Sie"
FEHLERMELDUNGS_STIL = "Beschreiben Sie Ursache, Auswirkung und nächsten Schritt."


# Zielgruppen im Dokumentationsfluss.
ZIELGRUPPE_ADMIN = "Admin"
ZIELGRUPPE_SUPPORT = "Support"
ZIELGRUPPE_DRITTUSER = "Drittuser"


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
BERICHT_ZUSAMMENFASSUNG = "Zusammenfassung"
BERICHT_BEFUNDE = "Befunde"
BERICHT_AUSWIRKUNGEN = "Auswirkungen"
BERICHT_SERVERLISTE = "Serverübersicht"
BERICHT_MASSNAHMEN = "Maßnahmen"
BERICHT_ARTEFAKTE = "Artefakte"


# Standardtexte rund um den Shell-Meldungsbereich.
SHELL_BEREICH_STATUS_MELDUNGEN = "Status / Meldungen"
SHELL_OPTION_TECHNISCHE_LOGS = "Technische Meldungen anzeigen"
SHELL_STATUS_BEREIT = "Bereit"


# Abschlussseite im Installer-Wizard.
INSTALLER_ABSCHLUSS_WAS_GETAN = "Was wurde getan"
INSTALLER_ABSCHLUSS_NAECHSTE_SCHRITTE = "Was ist als Nächstes zu tun?"


# Pfad-/Optionsschritt im Installer-Wizard.
INSTALLER_OPTIONEN_UEBERNEHMEN_BUTTON = "Auswahl übernehmen (nur für diesen Lauf)"
INSTALLER_OPTIONEN_UEBERNOMMEN_STATUS = "Optionen wurden übernommen."
INSTALLER_OPTIONEN_UEBERNOMMEN_LOG = "Auswahl wurde für diesen Lauf übernommen."
INSTALLER_OPTIONEN_HINWEIS_TEXT = (
    "Hinweis: Es wird keine Datei geschrieben. Die Auswahl gilt nur für den aktuellen "
    "Installationslauf. Die eigentliche Installation beginnt erst mit \"Installation starten\"."
)
INSTALLER_OPTIONEN_INFO_ICON_TOOLTIP = (
    "Übernimmt die aktuelle Auswahl nur temporär für den laufenden Wizard."
)

# Rückwärtskompatibler Alias für bestehende GUI-Importe.
BERICHT_MANAGEMENT_ZUSAMMENFASSUNG = BERICHT_ZUSAMMENFASSUNG
