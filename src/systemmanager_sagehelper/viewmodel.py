"""Transformationen zwischen Analysemodell und UI-/Reporting-ViewModel."""

from __future__ import annotations

from .models import (
    AnalyseErgebnis,
    PortDienstEintrag,
    RollenCheckEintrag,
    ServerDetailkarte,
)


def baue_server_detailkarte(ergebnis: AnalyseErgebnis) -> ServerDetailkarte:
    """Transformiert ein AnalyseErgebnis in eine konsistente Detailkarte.

    Die Detailkarte wird in GUI und Berichtsexport identisch verwendet,
    damit keine doppelte Mapping-Logik entsteht.
    """
    rollen_checks = [
        RollenCheckEintrag(
            rolle="SQL",
            erkannt=ergebnis.rollen_details.sql.erkannt,
            details=[
                f"Instanzen: {', '.join(ergebnis.rollen_details.sql.instanzen) or 'keine'}",
                f"Dienste: {', '.join(ergebnis.rollen_details.sql.dienste) or 'keine'}",
            ],
        ),
        RollenCheckEintrag(
            rolle="APP",
            erkannt=ergebnis.rollen_details.app.erkannt,
            details=[
                f"Sage-Pfade: {', '.join(ergebnis.rollen_details.app.sage_pfade) or 'keine'}",
                f"Sage-Versionen: {', '.join(ergebnis.rollen_details.app.sage_versionen) or 'keine'}",
            ],
        ),
        RollenCheckEintrag(
            rolle="CTX",
            erkannt=ergebnis.rollen_details.ctx.erkannt,
            details=[
                f"Terminaldienste: {', '.join(ergebnis.rollen_details.ctx.terminaldienste) or 'keine'}",
                f"Session-Indikatoren: {', '.join(ergebnis.rollen_details.ctx.session_indikatoren) or 'keine'}",
            ],
        ),
    ]

    ports_und_dienste = [
        PortDienstEintrag(
            typ="Port",
            name=str(port.port),
            status="offen" if port.offen else "blockiert/unerreichbar",
            details=port.bezeichnung,
        )
        for port in ergebnis.ports
    ]
    ports_und_dienste.extend(
        PortDienstEintrag(
            typ="Dienst",
            name=dienst.name,
            status=dienst.status or "unbekannt",
            details=dienst.starttyp,
        )
        for dienst in ergebnis.dienste
    )

    software = [f"{eintrag.name} {eintrag.version or ''}".strip() for eintrag in ergebnis.software] or list(
        ergebnis.installierte_anwendungen
    )
    empfehlungen = list(ergebnis.empfehlungen)
    empfehlungen.extend(
        f"Port {port.port} ({port.bezeichnung}) prüfen/freischalten" for port in ergebnis.ports if not port.offen
    )

    return ServerDetailkarte(
        server=ergebnis.server,
        zeitpunkt=ergebnis.zeitpunkt,
        rollen=list(ergebnis.rollen),
        rollenquelle=ergebnis.rollenquelle,
        betriebssystem=ergebnis.betriebssystem,
        os_version=ergebnis.os_version,
        rollen_checks=rollen_checks,
        ports_und_dienste=ports_und_dienste,
        software=software,
        empfehlungen=empfehlungen,
        freitext_hinweise=list(ergebnis.hinweise),
        kundenstammdaten=ergebnis.kundenstammdaten,
        netzwerkidentitaet=ergebnis.netzwerkidentitaet,
        cpu_details=ergebnis.cpu_details,
        dotnet_versionen=list(ergebnis.dotnet_versionen),
        firewall_regeln=ergebnis.firewall_regeln,
        sage_lizenz=ergebnis.sage_lizenz,
    )


def baue_server_detailkarten(ergebnisse: list[AnalyseErgebnis]) -> list[ServerDetailkarte]:
    """Erzeugt Detailkarten für eine Ergebnisliste."""
    return [baue_server_detailkarte(ergebnis) for ergebnis in ergebnisse]
