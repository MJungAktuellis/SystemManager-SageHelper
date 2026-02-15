"""Erzeugung von Markdown-Ausgaben für Microsoft Loop oder Wiki-Systeme."""

from __future__ import annotations

from .models import AnalyseErgebnis


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
                "",
                "### Portprüfung",
            ]
        )

        for port in ergebnis.ports:
            status = "✅ offen" if port.offen else "⚠️ blockiert/unerreichbar"
            zeilen.append(f"- {port.port} ({port.bezeichnung}): {status}")

        if ergebnis.hinweise:
            zeilen.append("")
            zeilen.append("### Hinweise")
            zeilen.extend(f"- {hinweis}" for hinweis in ergebnis.hinweise)

        zeilen.append("")

    return "\n".join(zeilen).strip() + "\n"
