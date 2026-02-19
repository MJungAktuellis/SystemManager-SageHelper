"""Erzeugung standardisierter Markdown-Berichte für Microsoft Loop oder technische Prüfungen."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from .models import AnalyseErgebnis, ServerDetailkarte
from .viewmodel import baue_server_detailkarte
from .texte import (
    BERICHT_ARTEFAKTE,
    BERICHT_AUSWIRKUNGEN,
    BERICHT_BEFUNDE,
    BERICHT_KOPFBEREICH,
    BERICHT_MASSNAHMEN,
    BERICHT_SERVERLISTE,
    BERICHT_TITEL,
    BERICHT_ZUSAMMENFASSUNG,
    ZIELGRUPPE_ADMIN,
    ZIELGRUPPE_DRITTUSER,
    ZIELGRUPPE_SUPPORT,
    STATUS_ERFOLG,
    STATUS_HINWEIS,
    STATUS_WARNUNG,
)

# Statische Versionskennung des Templates, damit Berichtsinhalte revisionssicher bleiben.
TEMPLATE_VERSION = "1.0"
Berichtsmodus = Literal["voll", "kurz"]



def _render_bullet_liste(eintraege: list[str], limit: int = 15) -> list[str]:
    """Formatiert eine Liste als konsistente Markdown-Aufzählung mit optionaler Begrenzung."""
    if not eintraege:
        return [f"- {STATUS_HINWEIS}: keine Einträge gefunden"]

    zeilen = [f"- {eintrag}" for eintrag in eintraege[:limit]]
    rest = len(eintraege) - limit
    if rest > 0:
        zeilen.append(f"- {STATUS_HINWEIS}: ... sowie {rest} weitere Einträge")
    return zeilen


def _render_tabelle(ueberschriften: list[str], zeilen: list[list[str]]) -> list[str]:
    """Erstellt eine Markdown-Tabelle in einheitlicher Formatierung."""
    if not zeilen:
        return ["| Hinweis |", "| --- |", f"| {STATUS_HINWEIS}: keine Daten vorhanden |"]

    kopf = "| " + " | ".join(ueberschriften) + " |"
    trenner = "| " + " | ".join("---" for _ in ueberschriften) + " |"
    inhalt = ["| " + " | ".join(zelle for zelle in zeile) + " |" for zeile in zeilen]
    return [kopf, trenner, *inhalt]


def _ermittle_lauf_id(ergebnisse: list[AnalyseErgebnis]) -> str:
    """Liest die Lauf-ID aus dem ersten Ergebnis oder liefert einen Platzhalter."""
    for ergebnis in ergebnisse:
        if ergebnis.lauf_id:
            return ergebnis.lauf_id
    return "nicht gesetzt"


def _baue_executive_summary(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Verdichtet die wichtigsten Kennzahlen als Management-Zusammenfassung."""
    gesamt = len(ergebnisse)
    server_mit_warnungen = 0
    offene_ports = 0
    blockierte_ports = 0

    for ergebnis in ergebnisse:
        hat_warnung = bool(ergebnis.hinweise)
        for port in ergebnis.ports:
            if port.offen:
                offene_ports += 1
            else:
                blockierte_ports += 1
                hat_warnung = True
        if hat_warnung:
            server_mit_warnungen += 1

    return [
        f"- {STATUS_HINWEIS}: Analysierte Server: {gesamt}",
        f"- {STATUS_ERFOLG}: Offene Ports (gesamt): {offene_ports}",
        f"- {STATUS_WARNUNG}: Blockierte/unerreichbare Ports (gesamt): {blockierte_ports}",
        f"- {STATUS_WARNUNG}: Server mit offenen Punkten: {server_mit_warnungen}",
    ]


def _baue_serverliste_tabelle(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Erstellt die tabellarische Serverübersicht für Management und Technik."""
    tabellenzeilen: list[list[str]] = []
    for ergebnis in ergebnisse:
        blockierte_ports = sum(1 for port in ergebnis.ports if not port.offen)
        status = STATUS_WARNUNG if blockierte_ports or ergebnis.hinweise else STATUS_ERFOLG
        tabellenzeilen.append(
            [
                ergebnis.server,
                ", ".join(ergebnis.rollen) if ergebnis.rollen else "nicht gesetzt",
                ergebnis.betriebssystem or "unbekannt",
                ergebnis.sage_version or "nicht erkannt",
                str(blockierte_ports),
                status,
            ]
        )
    return _render_tabelle(
        ["Server", "Rollen", "Betriebssystem", "Sage-Version", "Blockierte Ports", "Bewertung"],
        tabellenzeilen,
    )


def _baue_auswirkungen(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Leitet Auswirkungen aus Blockaden und Hinweisen ab."""
    auswirkungen: list[str] = []
    for ergebnis in ergebnisse:
        blockierte_ports = [str(port.port) for port in ergebnis.ports if not port.offen]
        if blockierte_ports:
            auswirkungen.append(
                f"{STATUS_WARNUNG}: {ergebnis.server} - Blockierte Ports ({', '.join(blockierte_ports)}) können Fachanwendungen stören."
            )
        if ergebnis.hinweise:
            auswirkungen.append(
                f"{STATUS_WARNUNG}: {ergebnis.server} - Offene Hinweise können Betrieb und Supportaufwand erhöhen."
            )

    if not auswirkungen:
        return [f"- {STATUS_ERFOLG}: Keine kritischen Auswirkungen erkannt."]
    return _render_bullet_liste(auswirkungen, limit=200)


def _baue_massnahmen(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Sammelt Maßnahmen und offene Punkte aus dem gemeinsamen ViewModel."""
    massnahmen: list[str] = []
    for ergebnis in ergebnisse:
        karte = baue_server_detailkarte(ergebnis)
        massnahmen.extend(f"{STATUS_WARNUNG}: {karte.server} - {eintrag}" for eintrag in karte.empfehlungen)
        massnahmen.extend(f"{STATUS_WARNUNG}: {karte.server} - {hinweis}" for hinweis in karte.freitext_hinweise)

    if not massnahmen:
        return [f"- {STATUS_ERFOLG}: Keine offenen Punkte erkannt."]
    return _render_bullet_liste(massnahmen, limit=200)


def _render_detailblock(ergebnis: AnalyseErgebnis) -> list[str]:
    """Erzeugt den technischen Detailblock je Server über das gemeinsame ViewModel."""
    karte: ServerDetailkarte = baue_server_detailkarte(ergebnis)
    os_details = ergebnis.betriebssystem_details
    hw_details = ergebnis.hardware_details
    zeilen = [
        f"## Server: {karte.server}",
        f"- Zeitpunkt: {karte.zeitpunkt.isoformat(timespec='seconds')}",
        f"- Lauf-ID: {ergebnis.lauf_id or 'nicht gesetzt'}",
        f"- Rollen: {', '.join(karte.rollen) if karte.rollen else 'nicht gesetzt'}",
        f"- Rollenquelle: {karte.rollenquelle or 'unbekannt'}",
        f"- Betriebssystem: {karte.betriebssystem or 'unbekannt'}",
        f"- OS-Version: {karte.os_version or 'unbekannt'}",
        f"- CPU (logische Kerne): {ergebnis.cpu_logische_kerne if ergebnis.cpu_logische_kerne is not None else 'unbekannt'}",
        f"- CPU-Modell: {ergebnis.cpu_modell or 'unbekannt'}",
        f"- Sage-Version: {ergebnis.sage_version or 'nicht erkannt'}",
        "- SQL Management Studio: " + (ergebnis.management_studio_version or "nicht erkannt"),
        "",
        "### Betriebssystem-Details",
        f"- Name: {os_details.name or 'unbekannt'}",
        f"- Version: {os_details.version or 'unbekannt'}",
        f"- Build: {os_details.build or 'unbekannt'}",
        f"- Architektur: {os_details.architektur or 'unbekannt'}",
        "",
        "### Hardware-Details",
        f"- CPU: {hw_details.cpu_modell or 'unbekannt'}",
        "- Logische Kerne: " + (str(hw_details.cpu_logische_kerne) if hw_details.cpu_logische_kerne is not None else "unbekannt"),
        "- Arbeitsspeicher (GB): " + (str(hw_details.arbeitsspeicher_gb) if hw_details.arbeitsspeicher_gb is not None else "unbekannt"),
        "",
        "### Rollenprüfung",
    ]
    for check in karte.rollen_checks:
        zeilen.append(f"- {check.rolle}: {'erkannt' if check.erkannt else 'nicht erkannt'} | {' | '.join(check.details)}")

    zeilen.extend(["", "### Portprüfung"])
    for eintrag in karte.ports_und_dienste:
        if eintrag.typ != "Port":
            continue
        status = f"{STATUS_ERFOLG}: offen" if eintrag.status == "offen" else f"{STATUS_WARNUNG}: blockiert/unerreichbar"
        zeilen.append(f"- {eintrag.name} ({eintrag.details or 'Port'}): {status}")

    zeilen.extend(["", "### Freigegebene/relevante Ports"])
    offene_ports = [f"{STATUS_ERFOLG}: {eintrag.name} ({eintrag.details or 'Port'})" for eintrag in karte.ports_und_dienste if eintrag.typ == 'Port' and eintrag.status == 'offen']
    zeilen.extend(_render_bullet_liste(offene_ports))

    zeilen.extend(["", "### Dienste (Auszug)"])
    zeilen.extend(_render_bullet_liste([f"{eintrag.name} ({eintrag.status})" for eintrag in karte.ports_und_dienste if eintrag.typ == 'Dienst']))

    zeilen.extend(["", "### Software (Auszug)"])
    zeilen.extend(_render_bullet_liste(karte.software))

    zeilen.extend(["", "### Partneranwendungen"])
    zeilen.extend(_render_bullet_liste(ergebnis.partner_anwendungen))

    zeilen.extend(["", "### Installierte Anwendungen (Auszug)"])
    zeilen.extend(_render_bullet_liste(ergebnis.installierte_anwendungen))

    if karte.freitext_hinweise:
        zeilen.extend(["", "### Hinweise"])
        zeilen.extend(f"- {STATUS_WARNUNG}: {hinweis}" for hinweis in karte.freitext_hinweise)

    zeilen.append("")
    return zeilen


def render_markdown(
    ergebnisse: list[AnalyseErgebnis],
    *,
    kunde: str = "nicht angegeben",
    umgebung: str = "nicht angegeben",
    template_version: str = TEMPLATE_VERSION,
    berichtsmodus: Berichtsmodus = "voll",
) -> str:
    """Formatiert Analyseergebnisse in ein standardisiertes Markdown-Dokument.

    Der Bericht unterstützt zwei Modi:
    - ``voll``: Vollbericht mit technischen Detailblöcken je Server.
    - ``kurz``: Kurzbericht für Management/Loop ohne tiefe technische Einzelwerte.
    """
    erzeugt_am = datetime.now().isoformat(timespec="seconds")
    lauf_id = _ermittle_lauf_id(ergebnisse)
    modus_name = "Vollbericht technisch" if berichtsmodus == "voll" else "Kurzbericht für Loop"

    zeilen: list[str] = [
        f"# {BERICHT_TITEL}",
        "",
        f"## {BERICHT_KOPFBEREICH}",
        f"- Kunde: {kunde}",
        f"- Umgebung: {umgebung}",
        f"- Datum: {erzeugt_am}",
        f"- Lauf-ID: {lauf_id}",
        f"- Berichtstyp: {modus_name}",
        f"- Zielgruppen: {ZIELGRUPPE_ADMIN}, {ZIELGRUPPE_SUPPORT}, {ZIELGRUPPE_DRITTUSER}",
        f"- Template-Version: {template_version}",
        "",
        f"## {BERICHT_ZUSAMMENFASSUNG}",
        *_baue_executive_summary(ergebnisse),
        "",
        f"## {BERICHT_SERVERLISTE}",
        *_baue_serverliste_tabelle(ergebnisse),
        "",
        f"## {BERICHT_BEFUNDE}",
        "- Befunde pro Server finden Sie im jeweiligen Detailblock.",
        "",
        f"## {BERICHT_AUSWIRKUNGEN}",
        *_baue_auswirkungen(ergebnisse),
        "",
    ]

    if berichtsmodus == "voll":
        zeilen.append("## Detailblöcke je Server")
        zeilen.append("")
        for ergebnis in ergebnisse:
            zeilen.extend(_render_detailblock(ergebnis))

    zeilen.extend([f"## {BERICHT_MASSNAHMEN}", *_baue_massnahmen(ergebnisse), ""])
    zeilen.extend([f"## {BERICHT_ARTEFAKTE}", "- Laufbezogene Artefakte sind im Dokumentationsbericht referenziert.", ""])
    return "\n".join(zeilen).strip() + "\n"
