"""Erzeugung von Markdown-Ausgaben für Microsoft Loop oder Wiki-Systeme."""

from __future__ import annotations

from .models import AnalyseErgebnis


def _render_liste_tabelle(eintraege: list[str], limit: int = 15) -> list[str]:
    """Formatiert eine Liste kompakt als Markdown-Aufzählung mit optionaler Begrenzung."""
    if not eintraege:
        return ["- keine Einträge gefunden"]

    zeilen = [f"- {eintrag}" for eintrag in eintraege[:limit]]
    rest = len(eintraege) - limit
    if rest > 0:
        zeilen.append(f"- ... sowie {rest} weitere Einträge")
    return zeilen


def _ermittle_lauf_id(ergebnisse: list[AnalyseErgebnis]) -> str:
    """Liest die Lauf-ID aus dem ersten Ergebnis oder liefert einen Platzhalter."""
    for ergebnis in ergebnisse:
        if ergebnis.lauf_id:
            return ergebnis.lauf_id
    return "nicht gesetzt"


def render_markdown(ergebnisse: list[AnalyseErgebnis]) -> str:
    """Formatiert Analyseergebnisse in ein gut lesbares Markdown-Dokument."""
    zeilen: list[str] = ["# Serverdokumentation", "", f"- Lauf-ID: {_ermittle_lauf_id(ergebnisse)}", ""]

    for ergebnis in ergebnisse:
        os_details = ergebnis.betriebssystem_details
        hw_details = ergebnis.hardware_details
        zeilen.extend(
            [
                f"## Server: {ergebnis.server}",
                f"- Zeitpunkt: {ergebnis.zeitpunkt.isoformat(timespec='seconds')}",
                f"- Lauf-ID: {ergebnis.lauf_id or 'nicht gesetzt'}",
                f"- Rollen: {', '.join(ergebnis.rollen) if ergebnis.rollen else 'nicht gesetzt'}",
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
        )

        for port in ergebnis.ports:
            status = "✅ offen" if port.offen else "⚠️ blockiert/unerreichbar"
            zeilen.append(f"- {port.port} ({port.bezeichnung}): {status}")

        zeilen.append("")
        zeilen.append("### Dienste (Auszug)")
        zeilen.extend(_render_liste_tabelle([f"{dienst.name} ({dienst.status or 'unbekannt'})" for dienst in ergebnis.dienste]))

        zeilen.append("")
        zeilen.append("### Software (Auszug)")
        zeilen.extend(
            _render_liste_tabelle(
                [
                    f"{eintrag.name} {eintrag.version}".strip() if eintrag.version else eintrag.name
                    for eintrag in ergebnis.software
                ]
            )
        )

        zeilen.append("")
        zeilen.append("### Partneranwendungen")
        zeilen.extend(_render_liste_tabelle(ergebnis.partner_anwendungen))

        zeilen.append("")
        zeilen.append("### Installierte Anwendungen (Auszug)")
        zeilen.extend(_render_liste_tabelle(ergebnis.installierte_anwendungen))

        if ergebnis.hinweise:
            zeilen.append("")
            zeilen.append("### Hinweise")
            zeilen.extend(f"- {hinweis}" for hinweis in ergebnis.hinweise)

        zeilen.append("")

    return "\n".join(zeilen).strip() + "\n"
