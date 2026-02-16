"""Analysefunktionen für lokale oder remote erreichbare Windows-Server."""

from __future__ import annotations

import platform
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Protocol

from .config import STANDARD_PORTS
from .logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from .models import (
    APPRollenDetails,
    AnalyseErgebnis,
    BetriebssystemDetails,
    CTXRollenDetails,
    DienstInfo,
    HardwareDetails,
    PortStatus,
    RollenDetails,
    SQLRollenDetails,
    ServerZiel,
    SoftwareInfo,
)

# Fachliche Zuordnung geöffneter Ports zu typischen Serverrollen.
_PORT_ROLLEN_MAPPING: dict[int, str] = {
    1433: "SQL",
    3389: "CTX",
}

# Schlüsselwörter für die Erkennung von Sage- und Partneranwendungen.
_SAGE_KEYWORDS = ["sage", "sage100"]
_PARTNER_KEYWORDS = ["dms", "crm", "edi", "shop", "bi", "isv"]
_MANAGEMENT_STUDIO_KEYWORDS = ["sql server management studio", "ssms"]
_SQL_SERVICE_KEYWORDS = ("mssql", "sql server", "sqlserveragent")
_CTX_SERVICE_KEYWORDS = ("termservice", "sessionenv", "umrdpservice", "rdp")

logger = konfiguriere_logger(__name__, dateiname="server_analysis.log")


@dataclass(frozen=True)
class SocketKandidat:
    """Kapselt einen konkreten Socket-Endpunkt für eine Portprüfung."""

    familie: int
    socktyp: int
    proto: int
    sockaddr: tuple


@dataclass(frozen=True)
class RemoteSystemdaten:
    """Einheitliche Struktur für Daten aus einem Remote-Provider (WMI/WinRM)."""

    betriebssystem: BetriebssystemDetails = field(default_factory=BetriebssystemDetails)
    hardware: HardwareDetails = field(default_factory=HardwareDetails)
    dienste: list[DienstInfo] = field(default_factory=list)
    software: list[SoftwareInfo] = field(default_factory=list)


class RemoteDatenProvider(Protocol):
    """Interface für austauschbare Remote-Adapter (z. B. WinRM oder WMI)."""

    def ist_verfuegbar(self) -> bool:
        """Liefert `True`, wenn der Adapter einsatzbereit ist."""

    def lese_systemdaten(self, server: str) -> RemoteSystemdaten | None:
        """Liest strukturierte Systemdaten für einen Zielserver."""


class WinRMAdapter:
    """Basisadapter für WinRM.

    Die produktive Implementierung kann hier später angebunden werden,
    ohne die fachliche Analysepipeline zu verändern.
    """

    def ist_verfuegbar(self) -> bool:
        return False

    def lese_systemdaten(self, server: str) -> RemoteSystemdaten | None:  # noqa: ARG002
        return None


class WMIAdapter:
    """Basisadapter für WMI.

    Der Adapter liefert aktuell noch keine Daten, stellt jedoch die
    saubere Integrationsstelle für spätere Erweiterungen bereit.
    """

    def ist_verfuegbar(self) -> bool:
        return False

    def lese_systemdaten(self, server: str) -> RemoteSystemdaten | None:  # noqa: ARG002
        return None


class KombinierterRemoteProvider:
    """Probiert mehrere Adapter in Reihenfolge aus und nutzt den ersten Treffer."""

    def __init__(self, adapter: Iterable[RemoteDatenProvider] | None = None) -> None:
        self._adapter = list(adapter) if adapter is not None else [WinRMAdapter(), WMIAdapter()]

    def ist_verfuegbar(self) -> bool:
        return any(a.ist_verfuegbar() for a in self._adapter)

    def lese_systemdaten(self, server: str) -> RemoteSystemdaten | None:
        for adapter in self._adapter:
            if not adapter.ist_verfuegbar():
                continue
            daten = adapter.lese_systemdaten(server)
            if daten is not None:
                return daten
        return None


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


def _ermittle_lokale_systeminventar() -> RemoteSystemdaten:
    """Liest lokal verfügbare Inventardaten ohne zusätzliche Abhängigkeiten aus."""
    import os

    software = [SoftwareInfo(name=paket) for paket in _normalisiere_liste_ohne_duplikate(_ermittle_python_paketnamen())]
    return RemoteSystemdaten(
        betriebssystem=BetriebssystemDetails(
            name=platform.system() or None,
            version=platform.version() or None,
            build=platform.release() or None,
            architektur=platform.machine() or None,
        ),
        hardware=HardwareDetails(
            cpu_logische_kerne=os.cpu_count(),
            cpu_modell=platform.processor() or None,
        ),
        software=software,
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


def _uebernehme_inventardaten(ergebnis: AnalyseErgebnis, inventar: RemoteSystemdaten) -> None:
    """Schreibt Inventardaten in das Ergebnis inkl. Rückwärtskompatibilität."""
    ergebnis.betriebssystem_details = inventar.betriebssystem
    ergebnis.hardware_details = inventar.hardware
    ergebnis.dienste = inventar.dienste
    ergebnis.software = inventar.software

    # Kompatibilitätsfelder für bestehende Reports/CLI.
    ergebnis.betriebssystem = inventar.betriebssystem.name or ergebnis.betriebssystem
    ergebnis.os_version = inventar.betriebssystem.version or ergebnis.os_version
    ergebnis.cpu_logische_kerne = inventar.hardware.cpu_logische_kerne
    ergebnis.cpu_modell = inventar.hardware.cpu_modell

    installierte = [
        f"{eintrag.name} {eintrag.version}".strip() if eintrag.version else eintrag.name
        for eintrag in inventar.software
        if eintrag.name
    ]
    ergebnis.installierte_anwendungen = _normalisiere_liste_ohne_duplikate(installierte)




def schlage_rollen_per_portsignatur_vor(server: str) -> list[str]:
    """Leitet einen schnellen Rollenvorschlag allein aus typischen Portsignaturen ab."""
    erkannte_rollen: list[str] = []
    for port, rolle in _PORT_ROLLEN_MAPPING.items():
        kandidaten = _ermittle_socket_kandidaten(server, port)
        if kandidaten and pruefe_tcp_port(kandidaten) and rolle not in erkannte_rollen:
            erkannte_rollen.append(rolle)

    # Fallback: Falls kein eindeutiger Indikator gefunden wurde, bleibt APP als Defaultrolle aktiv.
    if not erkannte_rollen:
        erkannte_rollen.append("APP")
    return erkannte_rollen

def _pruefe_rollen(ergebnis: AnalyseErgebnis) -> None:
    """Ermittelt strukturierte Rollenindikatoren aus Ports, Diensten und Software."""
    dienstnamen = [dienst.name.lower() for dienst in ergebnis.dienste]
    software_namen = [
        f"{eintrag.name} {eintrag.version}".strip() if eintrag.version else eintrag.name
        for eintrag in ergebnis.software
    ]

    sql_dienste = [dienst.name for dienst in ergebnis.dienste if any(k in dienst.name.lower() for k in _SQL_SERVICE_KEYWORDS)]
    sql_instanzen = [name for name in software_namen if "sql server" in name.lower()]
    sql_erkannt = bool(sql_dienste or sql_instanzen or any(p.offen and p.port == 1433 for p in ergebnis.ports))

    sage_eintraege = [eintrag for eintrag in ergebnis.software if any(k in eintrag.name.lower() for k in _SAGE_KEYWORDS)]
    sage_pfade = _normalisiere_liste_ohne_duplikate(
        eintrag.installationspfad or "" for eintrag in sage_eintraege
    )
    sage_versionen = _normalisiere_liste_ohne_duplikate(
        f"{eintrag.name} {eintrag.version}".strip() if eintrag.version else eintrag.name for eintrag in sage_eintraege
    )
    app_erkannt = bool(sage_pfade or sage_versionen)

    ctx_dienste = [dienst.name for dienst in ergebnis.dienste if any(k in dienst.name.lower() for k in _CTX_SERVICE_KEYWORDS)]
    ctx_indikatoren: list[str] = []
    if any(port.offen and port.port == 3389 for port in ergebnis.ports):
        ctx_indikatoren.append("RDP-Port 3389 erreichbar")
    if any("termservice" in name for name in dienstnamen):
        ctx_indikatoren.append("TermService erkannt")
    if any("sessionenv" in name for name in dienstnamen):
        ctx_indikatoren.append("SessionEnv erkannt")
    ctx_erkannt = bool(ctx_dienste or ctx_indikatoren)

    ergebnis.rollen_details = RollenDetails(
        sql=SQLRollenDetails(erkannt=sql_erkannt, instanzen=sql_instanzen, dienste=sql_dienste),
        app=APPRollenDetails(erkannt=app_erkannt, sage_pfade=sage_pfade, sage_versionen=sage_versionen),
        ctx=CTXRollenDetails(erkannt=ctx_erkannt, terminaldienste=ctx_dienste, session_indikatoren=ctx_indikatoren),
    )

    ergebnis.sage_version, ergebnis.partner_anwendungen, ergebnis.management_studio_version = _klassifiziere_anwendungen(
        software_namen
    )


def analysiere_server(
    ziel: ServerZiel,
    remote_provider: RemoteDatenProvider | None = None,
    lauf_id: str | None = None,
) -> AnalyseErgebnis:
    """Erstellt ein belastbares Analyseergebnis mit Portstatus und Hinweisen."""
    aktive_lauf_id = lauf_id or erstelle_lauf_id()
    setze_lauf_id(aktive_lauf_id)
    logger.info("Starte Serveranalyse für %s", ziel.name)

    ziel_rollen = _normalisiere_rollen(ziel.rollen)
    os_name, os_version = _ermittle_systeminformationen(ziel.name)
    ergebnis = AnalyseErgebnis(
        server=ziel.name.strip(),
        zeitpunkt=datetime.now(),
        lauf_id=aktive_lauf_id,
        rollen=ziel_rollen,
        rollenquelle=ziel.rollenquelle or None,
        auto_rollen=_normalisiere_rollen(ziel.auto_rollen),
        manuell_ueberschrieben=ziel.manuell_ueberschrieben,
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

    if not ergebnis.rollenquelle:
        ergebnis.rollenquelle = "automatisch erkannt" if not ziel_rollen else "manuell gesetzt"
    if ergebnis.manuell_ueberschrieben:
        ergebnis.rollenquelle = "nachträglich geändert"

    provider = remote_provider or KombinierterRemoteProvider()
    if os_name is not None:
        _uebernehme_inventardaten(ergebnis, _ermittle_lokale_systeminventar())
    else:
        remote_daten = provider.lese_systemdaten(ergebnis.server) if provider.ist_verfuegbar() else None
        if remote_daten is None:
            ergebnis.hinweise.append(
                "Remote-Ziel erkannt: CPU-, Dienst- und Softwaredetails benötigen einen aktiven WinRM/WMI-Adapter."
            )
        else:
            _uebernehme_inventardaten(ergebnis, remote_daten)

    _pruefe_rollen(ergebnis)

    if ergebnis.rollen_details.sql.erkannt:
        erkannte_rollen.add("SQL")
    if ergebnis.rollen_details.app.erkannt:
        erkannte_rollen.add("APP")
    if ergebnis.rollen_details.ctx.erkannt:
        erkannte_rollen.add("CTX")
    if not ergebnis.rollen and erkannte_rollen:
        ergebnis.rollen = sorted(erkannte_rollen)

    if platform.system().lower() != "windows":
        ergebnis.hinweise.append(
            "Analyse läuft nicht auf Windows; WMI/PowerShell-Details sind daher nicht aktiv."
        )

    logger.info("Serveranalyse abgeschlossen für %s", ergebnis.server)
    return ergebnis


def analysiere_mehrere_server(
    ziele: list[ServerZiel],
    max_worker: int = 6,
    remote_provider: RemoteDatenProvider | None = None,
    lauf_id: str | None = None,
) -> list[AnalyseErgebnis]:
    """Analysiert mehrere Server parallel für bessere Performance in größeren Umgebungen."""
    if not ziele:
        return []

    aktive_lauf_id = lauf_id or erstelle_lauf_id()
    setze_lauf_id(aktive_lauf_id)
    logger.info("Starte Mehrserveranalyse für %s Ziel(e) mit Lauf-ID %s", len(ziele), aktive_lauf_id)

    ergebnisse: list[AnalyseErgebnis] = []
    with ThreadPoolExecutor(max_workers=min(max_worker, len(ziele))) as executor:
        futures = [
            executor.submit(analysiere_server, ziel, remote_provider, aktive_lauf_id)
            for ziel in ziele
        ]
        for future in as_completed(futures):
            ergebnisse.append(future.result())

    logger.info("Mehrserveranalyse abgeschlossen mit Lauf-ID %s", aktive_lauf_id)
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
