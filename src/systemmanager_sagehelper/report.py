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


def render_markdown(ergebnisse: list[AnalyseErgebnis]) -> str:
    """Formatiert Analyseergebnisse in ein gut lesbares Markdown-Dokument."""
    zeilen: list[str] = ["# Serverdokumentation", ""]

    for ergebnis in ergebnisse:
        zeilen.extend(
            [
                f"## Server: {ergebnis.server}",
                f"- Zeitpunkt: {ergebnis.zeitpunkt.isoformat(timespec='seconds')}",
                f"- Rollen: {', '.join(ergebnis.rollen) if ergebnis.rollen else 'nicht gesetzt'}",
                f"- Betriebssystem: {ergebnis.betriebssystem or 'unbekannt'}",
                f"- OS-Version: {ergebnis.os_version or 'unbekannt'}",
                f"- CPU (logische Kerne): {ergebnis.cpu_logische_kerne if ergebnis.cpu_logische_kerne is not None else 'unbekannt'}",
                f"- CPU-Modell: {ergebnis.cpu_modell or 'unbekannt'}",
                f"- Sage-Version: {ergebnis.sage_version or 'nicht erkannt'}",
                (
                    "- SQL Management Studio: "
                    + (ergebnis.management_studio_version or "nicht erkannt")
                ),
                "",
                "### Portprüfung",
            ]
        )

        for port in ergebnis.ports:
            status = "✅ offen" if port.offen else "⚠️ blockiert/unerreichbar"
            zeilen.append(f"- {port.port} ({port.bezeichnung}): {status}")

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
