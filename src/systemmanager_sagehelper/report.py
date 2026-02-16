"""Erzeugung standardisierter Markdown-Berichte für Microsoft Loop oder technische Reviews."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from .models import AnalyseErgebnis

# Statische Versionskennung des Templates, damit Berichtsinhalte revisionssicher bleiben.
TEMPLATE_VERSION = "1.0"
Berichtsmodus = Literal["voll", "kurz"]

_STATUS_OK = "✅ OK"
_STATUS_WARNUNG = "⚠️ WARNUNG"
_STATUS_INFO = "ℹ️ INFO"


def _render_bullet_liste(eintraege: list[str], limit: int = 15) -> list[str]:
    """Formatiert eine Liste als konsistente Markdown-Aufzählung mit optionaler Begrenzung."""
    if not eintraege:
        return [f"- {_STATUS_INFO}: keine Einträge gefunden"]

    zeilen = [f"- {eintrag}" for eintrag in eintraege[:limit]]
    rest = len(eintraege) - limit
    if rest > 0:
        zeilen.append(f"- {_STATUS_INFO}: ... sowie {rest} weitere Einträge")
    return zeilen


def _render_tabelle(ueberschriften: list[str], zeilen: list[list[str]]) -> list[str]:
    """Erstellt eine Markdown-Tabelle in einheitlicher Formatierung."""
    if not zeilen:
        return ["| Hinweis |", "| --- |", f"| {_STATUS_INFO}: keine Daten vorhanden |"]

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
    """Verdichtet die wichtigsten Kennzahlen als Executive Summary."""
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
        f"- {_STATUS_INFO}: Analysierte Server: {gesamt}",
        f"- {_STATUS_OK}: Offene Ports (gesamt): {offene_ports}",
        f"- {_STATUS_WARNUNG}: Blockierte/unerreichbare Ports (gesamt): {blockierte_ports}",
        f"- {_STATUS_WARNUNG}: Server mit offenen Punkten: {server_mit_warnungen}",
    ]


def _baue_serverliste_tabelle(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Erstellt die tabellarische Serverübersicht für Management und Technik."""
    tabellenzeilen: list[list[str]] = []
    for ergebnis in ergebnisse:
        blockierte_ports = sum(1 for port in ergebnis.ports if not port.offen)
        status = _STATUS_WARNUNG if blockierte_ports or ergebnis.hinweise else _STATUS_OK
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
        ["Server", "Rollen", "Betriebssystem", "Sage-Version", "Blockierte Ports", "Status"],
        tabellenzeilen,
    )


def _baue_massnahmen(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Sammelt Maßnahmen und offene Punkte aus Ports und Hinweisen."""
    massnahmen: list[str] = []
    for ergebnis in ergebnisse:
        for port in ergebnis.ports:
            if not port.offen:
                massnahmen.append(
                    f"{_STATUS_WARNUNG}: {ergebnis.server} - Port {port.port} ({port.bezeichnung}) prüfen/freischalten"
                )
        for hinweis in ergebnis.hinweise:
            massnahmen.append(f"{_STATUS_WARNUNG}: {ergebnis.server} - {hinweis}")

    if not massnahmen:
        return [f"- {_STATUS_OK}: Keine offenen Punkte erkannt."]
    return _render_bullet_liste(massnahmen, limit=200)


def _render_detailblock(ergebnis: AnalyseErgebnis) -> list[str]:
    """Erzeugt den technischen Detailblock je Server für den Vollbericht."""
    os_details = ergebnis.betriebssystem_details
    hw_details = ergebnis.hardware_details
    zeilen = [
        f"## Server: {ergebnis.server}",
        f"- Zeitpunkt: {ergebnis.zeitpunkt.isoformat(timespec='seconds')}",
        f"- Lauf-ID: {ergebnis.lauf_id or 'nicht gesetzt'}",
        f"- Rollen: {', '.join(ergebnis.rollen) if ergebnis.rollen else 'nicht gesetzt'}",
        f"- Rollenquelle: {ergebnis.rollenquelle or 'unbekannt'}",
        f"- Auto-Rollenvorschlag: {', '.join(ergebnis.auto_rollen) if ergebnis.auto_rollen else 'nicht vorhanden'}",
        f"- Manuell überschrieben: {'ja' if ergebnis.manuell_ueberschrieben else 'nein'}",
        f"- Betriebssystem: {ergebnis.betriebssystem or 'unbekannt'}",
        f"- OS-Version: {ergebnis.os_version or 'unbekannt'}",
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
        (
            "- Logische Kerne: "
            + (str(hw_details.cpu_logische_kerne) if hw_details.cpu_logische_kerne is not None else "unbekannt")
        ),
        (
            "- Arbeitsspeicher (GB): "
            + (str(hw_details.arbeitsspeicher_gb) if hw_details.arbeitsspeicher_gb is not None else "unbekannt")
        ),
        "",
        "### Rollenprüfung",
        (
            "- SQL: "
            + ("erkannt" if ergebnis.rollen_details.sql.erkannt else "nicht erkannt")
            + f" | Instanzen: {', '.join(ergebnis.rollen_details.sql.instanzen) or 'keine'}"
            + f" | Dienste: {', '.join(ergebnis.rollen_details.sql.dienste) or 'keine'}"
        ),
        (
            "- APP: "
            + ("erkannt" if ergebnis.rollen_details.app.erkannt else "nicht erkannt")
            + f" | Sage-Pfade: {', '.join(ergebnis.rollen_details.app.sage_pfade) or 'keine'}"
            + f" | Sage-Versionen: {', '.join(ergebnis.rollen_details.app.sage_versionen) or 'keine'}"
        ),
        (
            "- CTX: "
            + ("erkannt" if ergebnis.rollen_details.ctx.erkannt else "nicht erkannt")
            + f" | Terminaldienste: {', '.join(ergebnis.rollen_details.ctx.terminaldienste) or 'keine'}"
            + f" | Session-Indikatoren: {', '.join(ergebnis.rollen_details.ctx.session_indikatoren) or 'keine'}"
        ),
        "",
        "### Portprüfung",
    ]

    for port in ergebnis.ports:
        status = f"{_STATUS_OK}: offen" if port.offen else f"{_STATUS_WARNUNG}: blockiert/unerreichbar"
        zeilen.append(f"- {port.port} ({port.bezeichnung}): {status}")

    zeilen.extend(["", "### Freigegebene/relevante Ports"])
    offene_ports = [f"{_STATUS_OK}: {port.port} ({port.bezeichnung})" for port in ergebnis.ports if port.offen]
    zeilen.extend(_render_bullet_liste(offene_ports))

    zeilen.extend(["", "### Dienste (Auszug)"])
    zeilen.extend(_render_bullet_liste([f"{dienst.name} ({dienst.status or 'unbekannt'})" for dienst in ergebnis.dienste]))

    zeilen.extend(["", "### Software (Auszug)"])
    zeilen.extend(
        _render_bullet_liste(
            [
                f"{eintrag.name} {eintrag.version}".strip() if eintrag.version else eintrag.name
                for eintrag in ergebnis.software
            ]
        )
    )

    zeilen.extend(["", "### Partneranwendungen"])
    zeilen.extend(_render_bullet_liste(ergebnis.partner_anwendungen))

    zeilen.extend(["", "### Installierte Anwendungen (Auszug)"])
    zeilen.extend(_render_bullet_liste(ergebnis.installierte_anwendungen))

    if ergebnis.hinweise:
        zeilen.extend(["", "### Hinweise"])
        zeilen.extend(f"- {_STATUS_WARNUNG}: {hinweis}" for hinweis in ergebnis.hinweise)

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
        "# Serverdokumentation",
        "",
        "## Kopfbereich",
        f"- Kunde: {kunde}",
        f"- Umgebung: {umgebung}",
        f"- Datum: {erzeugt_am}",
        f"- Lauf-ID: {lauf_id}",
        f"- Berichtstyp: {modus_name}",
        f"- Template-Version: {template_version}",
        "",
        "## Executive Summary",
        *_baue_executive_summary(ergebnisse),
        "",
        "## Serverliste",
        *_baue_serverliste_tabelle(ergebnisse),
        "",
    ]

    if berichtsmodus == "voll":
        zeilen.append("## Detailblöcke je Server")
        zeilen.append("")
        for ergebnis in ergebnisse:
            zeilen.extend(_render_detailblock(ergebnis))

    zeilen.extend(["## Maßnahmen/Offene Punkte", *_baue_massnahmen(ergebnisse), ""])
    return "\n".join(zeilen).strip() + "\n"
