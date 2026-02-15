"""Analysefunktionen für lokale oder remote erreichbare Windows-Server."""

from __future__ import annotations

import platform
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .config import STANDARD_PORTS
from .models import AnalyseErgebnis, PortStatus, ServerZiel

# Fachliche Zuordnung geöffneter Ports zu typischen Serverrollen.
_PORT_ROLLEN_MAPPING: dict[int, str] = {
    1433: "SQL",
    3389: "CTX",
}

# Schlüsselwörter für die Erkennung von Sage- und Partneranwendungen.
_SAGE_KEYWORDS = ["sage", "sage100"]
_PARTNER_KEYWORDS = ["dms", "crm", "edi", "shop", "bi", "isv"]
_MANAGEMENT_STUDIO_KEYWORDS = ["sql server management studio", "ssms"]


@dataclass(frozen=True)
class SocketKandidat:
    """Kapselt einen konkreten Socket-Endpunkt für eine Portprüfung."""

    familie: int
    socktyp: int
    proto: int
    sockaddr: tuple


@dataclass(frozen=True)
class Systeminventar:
    """Hält lokal auslesbare Systemdaten für eine strukturierte Ergebnisanzeige."""

    cpu_logische_kerne: int | None
    cpu_modell: str | None
    installierte_anwendungen: list[str]


def _normalisiere_rollen(rollen: list[str]) -> list[str]:
    """Normalisiert Rollen robust (trim, upper, ohne Duplikate, Reihenfolge bleibt)."""
    normalisiert: list[str] = []
    for rolle in rollen:
        kandidat = rolle.strip().upper()
        if kandidat and kandidat not in normalisiert:
            normalisiert.append(kandidat)
    return normalisiert


def _normalisiere_liste_ohne_duplikate(eintraege: Iterable[str]) -> list[str]:
    """Entfernt Leereinträge/Duplikate und erhält die ursprüngliche Reihenfolge."""
    ergebnis: list[str] = []
    for eintrag in eintraege:
        kandidat = eintrag.strip()
        if kandidat and kandidat not in ergebnis:
            ergebnis.append(kandidat)
    return ergebnis


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


def _ermittle_lokale_systeminventar() -> Systeminventar:
    """Liest lokal verfügbare Inventardaten ohne zusätzliche Abhängigkeiten aus."""
    # Best-Practice: zuverlässige Kernanzahl über os.cpu_count.
    import os

    cpu_logische_kerne = os.cpu_count()
    cpu_modell = platform.processor() or None

    # Ohne Windows-WMI-Abhängigkeiten erfassen wir nur lokal installierte Python-Pakete als Basis.
    # Dadurch bleibt das Tool portabel und stabil, bis ein optionales WMI-Plugin ergänzt wird.
    anwendungen = _normalisiere_liste_ohne_duplikate(_ermittle_python_paketnamen())
    return Systeminventar(
        cpu_logische_kerne=cpu_logische_kerne,
        cpu_modell=cpu_modell,
        installierte_anwendungen=anwendungen,
    )


def _ermittle_python_paketnamen() -> list[str]:
    """Liest Paketnamen der aktuellen Python-Umgebung als installierte Softwarebasis."""
    try:
        from importlib.metadata import distributions
    except Exception:
        return []

    pakete: list[str] = []
    for dist in distributions():
        name = dist.metadata.get("Name")
        version = dist.version
        if name:
            pakete.append(f"{name} {version}")
    return pakete


def _klassifiziere_anwendungen(anwendungen: list[str]) -> tuple[str | None, list[str], str | None]:
    """Erkennt Sage/Partner/SSMS aus einer Anwendungsliste per Schlüsselwörtern."""
    sage_version: str | None = None
    partner_apps: list[str] = []
    management_studio_version: str | None = None

    for app in anwendungen:
        lower_app = app.lower()

        if sage_version is None and any(keyword in lower_app for keyword in _SAGE_KEYWORDS):
            sage_version = app

        if any(keyword in lower_app for keyword in _PARTNER_KEYWORDS):
            partner_apps.append(app)

        if management_studio_version is None and any(
            keyword in lower_app for keyword in _MANAGEMENT_STUDIO_KEYWORDS
        ):
            management_studio_version = app

    return sage_version, _normalisiere_liste_ohne_duplikate(partner_apps), management_studio_version


def _analysiere_port(port: int, server: str) -> PortStatus:
    """Analysiert einen einzelnen Port für parallele Ausführung."""
    kandidaten = _ermittle_socket_kandidaten(server, port)
    port_info = next(item for item in STANDARD_PORTS if item.port == port)
    offen = pruefe_tcp_port(kandidaten)
    return PortStatus(port=port, offen=offen, bezeichnung=port_info.bezeichnung)


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
    ports = [port_info.port for port_info in STANDARD_PORTS]
    with ThreadPoolExecutor(max_workers=min(8, len(ports) or 1)) as executor:
        futures = [executor.submit(_analysiere_port, port, ergebnis.server) for port in ports]
        for future in as_completed(futures):
            status = future.result()
            ergebnis.ports.append(status)
            if status.offen and status.port in _PORT_ROLLEN_MAPPING:
                erkannte_rollen.add(_PORT_ROLLEN_MAPPING[status.port])

    ergebnis.ports.sort(key=lambda item: item.port)

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

    # Lokale Detailanalyse (CPU + installierte Anwendungen) nur für lokale Ziele.
    if os_name is not None:
        inventar = _ermittle_lokale_systeminventar()
        ergebnis.cpu_logische_kerne = inventar.cpu_logische_kerne
        ergebnis.cpu_modell = inventar.cpu_modell
        ergebnis.installierte_anwendungen = inventar.installierte_anwendungen
        (
            ergebnis.sage_version,
            ergebnis.partner_anwendungen,
            ergebnis.management_studio_version,
        ) = _klassifiziere_anwendungen(ergebnis.installierte_anwendungen)
    else:
        ergebnis.hinweise.append(
            "Remote-Ziel erkannt: CPU- und Softwaredetails benötigen ein Windows-Remote-Plugin (WMI/WinRM)."
        )

    if platform.system().lower() != "windows":
        ergebnis.hinweise.append(
            "Analyse läuft nicht auf Windows; WMI/PowerShell-Details sind daher nicht aktiv."
        )

    return ergebnis


def analysiere_mehrere_server(ziele: list[ServerZiel], max_worker: int = 6) -> list[AnalyseErgebnis]:
    """Analysiert mehrere Server parallel für bessere Performance in größeren Umgebungen."""
    if not ziele:
        return []

    ergebnisse: list[AnalyseErgebnis] = []
    with ThreadPoolExecutor(max_workers=min(max_worker, len(ziele))) as executor:
        futures = [executor.submit(analysiere_server, ziel) for ziel in ziele]
        for future in as_completed(futures):
            ergebnisse.append(future.result())

    # Ergebnisliste stabil nach Servername sortieren.
    return sorted(ergebnisse, key=lambda item: item.server.lower())


def entdecke_server_kandidaten(basis: str, start: int, ende: int) -> list[str]:
    """Sucht erreichbare Hosts in einem IPv4-Subnetz über DNS- und Port-Signaturen."""
    if start > ende:
        start, ende = ende, start

    kandidaten: list[str] = []
    for host_teil in range(start, ende + 1):
        host = f"{basis}.{host_teil}"
        if _ermittle_ip_adressen(host):
            kandidaten.append(host)
    return kandidaten
