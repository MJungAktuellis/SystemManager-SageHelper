"""Analysefunktionen für lokale oder remote erreichbare Windows-Server."""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass
from datetime import datetime

from .config import STANDARD_PORTS
from .models import AnalyseErgebnis, PortStatus, ServerZiel

# Fachliche Zuordnung geöffneter Ports zu typischen Serverrollen.
_PORT_ROLLEN_MAPPING: dict[int, str] = {
    1433: "SQL",
    3389: "CTX",
}


@dataclass(frozen=True)
class SocketKandidat:
    """Kapselt einen konkreten Socket-Endpunkt für eine Portprüfung."""

    familie: int
    socktyp: int
    proto: int
    sockaddr: tuple


def _normalisiere_rollen(rollen: list[str]) -> list[str]:
    """Normalisiert Rollen robust (trim, upper, ohne Duplikate, Reihenfolge bleibt)."""
    normalisiert: list[str] = []
    for rolle in rollen:
        kandidat = rolle.strip().upper()
        if kandidat and kandidat not in normalisiert:
            normalisiert.append(kandidat)
    return normalisiert


def _ermittle_ip_adressen(host: str) -> list[str]:
    """Löst einen Hostnamen robust auf und liefert eindeutige IPv4/IPv6-Adressen."""
    adressen: list[str] = []
    try:
        for eintrag in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP):
            ip_adresse = eintrag[4][0]
            if ip_adresse not in adressen:
                adressen.append(ip_adresse)
    except socket.gaierror:
        return []
    return adressen


def _ermittle_socket_kandidaten(host: str, port: int) -> list[SocketKandidat]:
    """Ermittelt alle Socket-Kandidaten für einen Host/Port oder liefert leer bei DNS-Fehlern."""
    try:
        kandidaten = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []

    return [
        SocketKandidat(familie=familie, socktyp=socktyp, proto=proto, sockaddr=sockaddr)
        for familie, socktyp, proto, _kanonisch, sockaddr in kandidaten
    ]


def pruefe_tcp_port(kandidaten: list[SocketKandidat], timeout: float = 0.8) -> bool:
    """Prüft effizient, ob mindestens ein Socket-Kandidat erreichbar ist."""
    for kandidat in kandidaten:
        try:
            with socket.socket(kandidat.familie, kandidat.socktyp, kandidat.proto) as sock:
                sock.settimeout(timeout)
                if sock.connect_ex(kandidat.sockaddr) == 0:
                    return True
        except OSError:
            # Einzelne fehlerhafte Kandidaten sollen die Gesamtauswertung nicht abbrechen.
            continue
    return False


def _ermittle_systeminformationen(zielname: str) -> tuple[str | None, str | None]:
    """Liefert OS-Daten für lokale Ziele; für Remote-Ziele bleibt der Wert unbekannt."""
    lokale_aliase = {"localhost", "127.0.0.1", "::1", socket.gethostname().lower()}
    if zielname.lower() in lokale_aliase:
        return platform.system(), platform.version()
    return None, None


def analysiere_server(ziel: ServerZiel) -> AnalyseErgebnis:
    """Erstellt ein belastbares Analyseergebnis mit Portstatus und Hinweisen."""
    ziel_rollen = _normalisiere_rollen(ziel.rollen)
    os_name, os_version = _ermittle_systeminformationen(ziel.name)
    ergebnis = AnalyseErgebnis(
        server=ziel.name.strip(),
        zeitpunkt=datetime.now(),
        rollen=ziel_rollen,
        betriebssystem=os_name,
        os_version=os_version,
    )

    ip_adressen = _ermittle_ip_adressen(ergebnis.server)
    if not ip_adressen:
        ergebnis.hinweise.append(
            "Hostname konnte nicht aufgelöst werden. Bitte DNS/Netzwerkverbindung prüfen."
        )

    erkannte_rollen: set[str] = set()
    for port_info in STANDARD_PORTS:
        kandidaten = _ermittle_socket_kandidaten(ergebnis.server, port_info.port)
        offen = pruefe_tcp_port(kandidaten)
        ergebnis.ports.append(
            PortStatus(port=port_info.port, offen=offen, bezeichnung=port_info.bezeichnung)
        )

        if offen and port_info.port in _PORT_ROLLEN_MAPPING:
            erkannte_rollen.add(_PORT_ROLLEN_MAPPING[port_info.port])

    if ip_adressen:
        ergebnis.hinweise.append(f"Aufgelöste Adressen: {', '.join(ip_adressen)}")

    if erkannte_rollen and ziel_rollen:
        fehlende_rollen = sorted(set(ziel_rollen) - erkannte_rollen)
        if fehlende_rollen:
            ergebnis.hinweise.append(
                "Folgende erwartete Rollen konnten per Portprofil nicht bestätigt werden: "
                + ", ".join(fehlende_rollen)
            )
    elif erkannte_rollen and not ziel_rollen:
        ergebnis.rollen = sorted(erkannte_rollen)

    if platform.system().lower() != "windows":
        ergebnis.hinweise.append(
            "Analyse läuft nicht auf Windows; WMI/PowerShell-Details sind daher nicht aktiv."
        )

    return ergebnis
