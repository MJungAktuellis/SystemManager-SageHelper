"""Analysefunktionen für lokale oder remote erreichbare Windows-Server."""

from __future__ import annotations

import json
import os
import platform
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Protocol

from .config import DISCOVERY_TCP_PORTS, STANDARD_PORTS
from .logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from .models import (
    DiscoveryErgebnis,
    APPRollenDetails,
    AnalyseErgebnis,
    BetriebssystemDetails,
    CPUDetails,
    CTXRollenDetails,
    DienstInfo,
    DotNetVersion,
    FirewallRegel,
    FirewallRegelsatz,
    HardwareDetails,
    Netzwerkidentitaet,
    PortStatus,
    RollenDetails,
    SQLDatenpfadInfo,
    SQLInstanzInfo,
    SQLRollenDetails,
    SageLizenzDetails,
    ServerZiel,
    SoftwareInfo,
)

# Fachliche Zuordnung geöffneter Ports zu typischen Serverrollen.
# APP- und CTX-Indikatoren werden gleichberechtigt neben SQL ausgewertet.
_PORT_ROLLEN_MAPPING: dict[int, str] = {
    1433: "SQL",
    1434: "SQL",
    4022: "SQL",
    80: "APP",
    443: "APP",
    8080: "APP",
    8443: "APP",
    3389: "CTX",
}

# Zentrales Rollen-Portprofil für Discovery-Signaturen je Serverrolle.
ROLLEN_PORTPROFILE: dict[str, dict[str, tuple[int, ...] | tuple[str, ...]]] = {
    "SQL": {
        "ports": (1433, 1434, 4022),
        "diensthinweise": ("mssql", "sql", "sqlbrowser", "sqlserveragent"),
    },
    "APP": {
        "ports": (80, 443, 8080, 8443),
        "diensthinweise": ("w3svc", "world wide web", "http", "tomcat", "iis"),
    },
    "CTX": {
        "ports": (3389,),
        "diensthinweise": ("termservice", "sessionenv", "umrdpservice", "rdp"),
    },
}

# Schlüsselwörter für die Erkennung von Sage- und Partneranwendungen.
_SAGE_KEYWORDS = ["sage", "sage100"]
_PARTNER_KEYWORDS = ["dms", "crm", "edi", "shop", "bi", "isv"]
_MANAGEMENT_STUDIO_KEYWORDS = ["sql server management studio", "ssms"]
_SQL_SERVICE_KEYWORDS = ("mssql", "sql server", "sqlserveragent")
_CTX_SERVICE_KEYWORDS = ("termservice", "sessionenv", "umrdpservice", "rdp")

# Präfixe zur strukturierten Fehlerklassifikation für Remote-Ziele.
_HINWEIS_DNS = "[DNS]"
_HINWEIS_AUTH = "[AUTH]"
_HINWEIS_WINRM = "[WINRM]"
_HINWEIS_TIMEOUT = "[TIMEOUT]"

logger = konfiguriere_logger(__name__, dateiname="server_analysis.log")


@dataclass(frozen=True)
class DiscoveryKonfiguration:
    """Steuert Strategien, Timeouts und Parallelität eines Discovery-Laufs."""

    ping_timeout: float = 0.8
    tcp_timeout: float = 0.5
    max_worker: int = 48
    tcp_ports: tuple[int, ...] = DISCOVERY_TCP_PORTS
    nutze_reverse_dns: bool = True
    nutze_ad_ldap: bool = False
    min_vertrauensgrad: float = 0.4


@dataclass(frozen=True)
class DiscoveryLaufProtokoll:
    """Verdichtete Laufmetrik inklusive Strategie- und Fehlerübersicht."""

    basis: str
    start: int
    ende: int
    strategien: tuple[str, ...]
    trefferzahl: int
    fehlerursachen: dict[str, int]


@dataclass(frozen=True)
class DiscoveryRangeSegment:
    """Beschreibt einen einzelnen Discovery-Range als wiederverwendbares Modell."""

    basis: str
    start: int
    ende: int

    def als_text(self) -> str:
        """Liefert ein gut lesbares Segmentformat für Logging und GUI."""
        return f"{self.basis}.{self.start}-{self.ende}"


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
    netzwerkidentitaet: Netzwerkidentitaet = field(default_factory=Netzwerkidentitaet)
    cpu_details: CPUDetails = field(default_factory=CPUDetails)
    dotnet_versionen: list[DotNetVersion] = field(default_factory=list)
    firewall_regeln: FirewallRegelsatz = field(default_factory=FirewallRegelsatz)
    sage_lizenz: SageLizenzDetails = field(default_factory=SageLizenzDetails)
    dienste: list[DienstInfo] = field(default_factory=list)
    software: list[SoftwareInfo] = field(default_factory=list)
    sql_instanzen: list[SQLInstanzInfo] = field(default_factory=list)


@dataclass(frozen=True)
class RemoteAbrufFehler(Exception):
    """Domänenspezifischer Fehler mit Klassifikation für Hinweise im Analysebericht."""

    kategorie: str
    nachricht: str


class RemoteDatenProvider(Protocol):
    """Interface für austauschbare Remote-Adapter (z. B. WinRM oder WMI)."""

    def ist_verfuegbar(self) -> bool:
        """Liefert `True`, wenn der Adapter einsatzbereit ist."""

    def lese_systemdaten(self, server: str) -> RemoteSystemdaten | None:
        """Liest strukturierte Systemdaten für einen Zielserver."""


class WinRMAdapter:
    """Produktiver WinRM-Adapter auf Basis von PowerShell-Remoting.

    Die Implementierung nutzt bewusst PowerShell als kleinsten gemeinsamen Nenner,
    damit keine zusätzlichen Python-Abhängigkeiten erforderlich sind.
    """

    def _fuehre_powershell_aus(self, command: str, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
        """Führt einen PowerShell-Befehl robust aus und liefert den Prozess zurück."""
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _klassifiziere_fehler(self, fehler: str) -> RemoteAbrufFehler:
        """Ordnet typische PowerShell-/WinRM-Fehler einer stabilen Kategorie zu."""
        text = fehler.lower()
        if any(token in text for token in ["timed out", "timeout", "operationtimedout"]):
            return RemoteAbrufFehler(_HINWEIS_TIMEOUT, "Zeitüberschreitung bei WinRM-Verbindung.")
        if any(token in text for token in ["access is denied", "unauthorized", "authentication"]):
            return RemoteAbrufFehler(_HINWEIS_AUTH, "Authentifizierung am Zielserver fehlgeschlagen.")
        if any(token in text for token in ["winrm", "wsman", "client cannot connect"]):
            return RemoteAbrufFehler(_HINWEIS_WINRM, "WinRM ist nicht konfiguriert oder nicht erreichbar.")
        return RemoteAbrufFehler(_HINWEIS_WINRM, "Unbekannter WinRM-Fehler beim Abruf der Systemdaten.")

    def ist_verfuegbar(self) -> bool:
        """Prüft, ob lokale PowerShell und WinRM grundsätzlich genutzt werden können."""
        try:
            pruefung = self._fuehre_powershell_aus("$PSVersionTable.PSVersion.ToString(); Test-WSMan -ErrorAction Stop | Out-Null", timeout=8.0)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return pruefung.returncode == 0

    def lese_systemdaten(self, server: str) -> RemoteSystemdaten | None:
        """Liest Inventardaten per Invoke-Command und parst das JSON-Ergebnis."""
        script_block = r"""
$ErrorActionPreference = 'Stop'
$remoteScript = {
    $os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfLogicalProcessors, NumberOfCores, MaxClockSpeed

    $cs = Get-CimInstance Win32_ComputerSystem
    $ramBytes = $cs.TotalPhysicalMemory
    $netzwerk = [System.Net.Dns]::GetHostEntry($env:COMPUTERNAME)

    $dotnetVersionen = @()
    $dotnetRelease = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue).Release
    if ($dotnetRelease) {
        $dotnetVersionen += [pscustomobject]@{ Produkt='NET Framework 4.x'; Version=[string]$dotnetRelease; Quelle='Registry' }
    }
    $dotnetVersionen += Get-ChildItem 'HKLM:\SOFTWARE\dotnet\Setup\InstalledVersions\x64\sharedfx\Microsoft.NETCore.App' -ErrorAction SilentlyContinue |
        Select-Object @{N='Produkt';E={'NET Runtime'}}, @{N='Version';E={$_.PSChildName}}, @{N='Quelle';E={'Registry'}}

    $firewallRegeln = Get-NetFirewallRule -ErrorAction SilentlyContinue |
        Where-Object { $_.Enabled -eq 'True' -and $_.Direction -in @('Inbound','Outbound') } |
        ForEach-Object {
            $regel = $_
            $portFilter = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $regel -ErrorAction SilentlyContinue | Select-Object -First 1
            [pscustomobject]@{
                Name = [string]$regel.DisplayName
                Richtung = [string]$regel.Direction
                Protokoll = [string]$portFilter.Protocol
                Aktion = [string]$regel.Action
                Port = [string]$portFilter.LocalPort
                Aktiviert = $regel.Enabled -eq 'True'
            }
        }

    $software = @()
    foreach ($root in @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )) {
        if (Test-Path $root) {
            $software += Get-ItemProperty $root -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName } |
                Select-Object @{N='Name';E={$_.DisplayName}}, @{N='Version';E={$_.DisplayVersion}}, @{N='Hersteller';E={$_.Publisher}}, @{N='Installationspfad';E={$_.InstallLocation}}
        }
    }

    $sageLizenz = [pscustomobject]@{
        Produkt = ($software | Where-Object { $_.Name -match 'Sage' } | Select-Object -First 1 -ExpandProperty Name)
        Version = ($software | Where-Object { $_.Name -match 'Sage' } | Select-Object -First 1 -ExpandProperty Version)
        Build = $null
        Lizenznehmer = $null
        Lizenzschluessel = $null
        Lizenztyp = $null
    }

    $dienste = Get-Service |
        Where-Object {
            $_.Name -match 'MSSQL|SQLSERVERAGENT|TermService|SessionEnv|UmRdpService|Rdp' -or
            $_.DisplayName -match 'SQL|Terminal|Remote Desktop'
        } |
        Select-Object Name, Status, StartType

    $instanzMap = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL' -ErrorAction SilentlyContinue)
    $sqlInstanzen = @()
    if ($instanzMap) {
        foreach ($prop in $instanzMap.PSObject.Properties) {
            if ($prop.Name -in @('PSPath','PSParentPath','PSChildName','PSDrive','PSProvider')) { continue }
            $instanzName = $prop.Name
            $instanzId = [string]$prop.Value
            $setupPath = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instanzId\Setup"
            $mssqlPath = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instanzId\MSSQLServer"
            $setup = Get-ItemProperty $setupPath -ErrorAction SilentlyContinue
            $mssql = Get-ItemProperty $mssqlPath -ErrorAction SilentlyContinue
            $datenpfade = @()
            foreach ($entry in @(
                @{ Kategorie = 'DataRoot'; Wert = $mssql.DefaultData },
                @{ Kategorie = 'LogRoot'; Wert = $mssql.DefaultLog },
                @{ Kategorie = 'BackupRoot'; Wert = $mssql.BackupDirectory },
                @{ Kategorie = 'MasterData'; Wert = $mssql.DefaultData },
                @{ Kategorie = 'MasterLog'; Wert = $mssql.DefaultLog }
            )) {
                if ($entry.Wert) {
                    $datenpfade += [pscustomobject]@{
                        Instanzname = $instanzName
                        Kategorie = $entry.Kategorie
                        Pfad = [string]$entry.Wert
                    }
                }
            }

            $sqlInstanzen += [pscustomobject]@{
                Instanzname = $instanzName
                InstanzId = $instanzId
                Version = [string]$setup.Version
                Edition = [string]$setup.Edition
                Datenpfade = $datenpfade
            }
        }
    }

    [pscustomobject]@{
        Betriebssystem = [pscustomobject]@{
            Name = [string]$os.Caption
            Version = [string]$os.Version
            Build = [string]$os.BuildNumber
            Architektur = [string]$os.OSArchitecture
        }
        Hardware = [pscustomobject]@{
            CpuModell = [string]$cpu.Name
            CpuLogischeKerne = [int]$cpu.NumberOfLogicalProcessors
            ArbeitsspeicherGB = [math]::Round($ramBytes / 1GB, 2)
        }
        Netzwerkidentitaet = [pscustomobject]@{
            Hostname = [string]$env:COMPUTERNAME
            FQDN = [string]$netzwerk.HostName
            Domain = [string]$cs.Domain
            IPAdressen = @($netzwerk.AddressList | ForEach-Object { $_.IPAddressToString })
        }
        CPUDetails = [pscustomobject]@{
            PhysischeKerne = [int]$cpu.NumberOfCores
            LogischeThreads = [int]$cpu.NumberOfLogicalProcessors
            TaktMHz = [double]$cpu.MaxClockSpeed
        }
        DotNetVersionen = ($dotnetVersionen | Sort-Object Version -Unique)
        FirewallRegeln = $firewallRegeln
        SageLizenz = $sageLizenz
        Dienste = $dienste
        Software = ($software | Sort-Object Name -Unique)
        SqlInstanzen = $sqlInstanzen
    }
}
Invoke-Command -ComputerName '__SERVER__' -ScriptBlock $remoteScript -ErrorAction Stop |
    ConvertTo-Json -Depth 8 -Compress
""".replace("__SERVER__", server)

        try:
            prozess = self._fuehre_powershell_aus(script_block, timeout=60.0)
        except FileNotFoundError:
            raise RemoteAbrufFehler(_HINWEIS_WINRM, "PowerShell ist auf dem Analysehost nicht verfügbar.")
        except subprocess.TimeoutExpired:
            raise RemoteAbrufFehler(_HINWEIS_TIMEOUT, f"Zeitüberschreitung beim Abruf von '{server}'.")

        if prozess.returncode != 0:
            raise self._klassifiziere_fehler((prozess.stderr or prozess.stdout).strip())

        roh = prozess.stdout.strip()
        if not roh:
            raise RemoteAbrufFehler(_HINWEIS_WINRM, "WinRM lieferte keine auswertbaren Daten zurück.")

        try:
            daten = json.loads(roh)
        except json.JSONDecodeError as exc:
            raise RemoteAbrufFehler(_HINWEIS_WINRM, f"Ungültige JSON-Antwort von WinRM: {exc.msg}")

        if not isinstance(daten, dict):
            raise RemoteAbrufFehler(_HINWEIS_WINRM, "Unerwartetes Antwortformat aus WinRM.")

        return _baue_remote_systemdaten_aus_json(daten)


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


def _json_liste(rohwert: object) -> list[dict]:
    """Normalisiert JSON-Felder auf eine Liste von Objekten."""
    if isinstance(rohwert, list):
        return [eintrag for eintrag in rohwert if isinstance(eintrag, dict)]
    if isinstance(rohwert, dict):
        return [rohwert]
    return []


def _baue_remote_systemdaten_aus_json(daten: dict) -> RemoteSystemdaten:
    """Mapped PowerShell-JSON robust in die internen Dataklassen."""
    os_daten = daten.get("Betriebssystem") if isinstance(daten.get("Betriebssystem"), dict) else {}
    hw_daten = daten.get("Hardware") if isinstance(daten.get("Hardware"), dict) else {}
    netz_daten = daten.get("Netzwerkidentitaet") if isinstance(daten.get("Netzwerkidentitaet"), dict) else {}
    cpu_daten = daten.get("CPUDetails") if isinstance(daten.get("CPUDetails"), dict) else {}
    sage_daten = daten.get("SageLizenz") if isinstance(daten.get("SageLizenz"), dict) else {}

    software = [
        SoftwareInfo(
            name=str(eintrag.get("Name") or "").strip(),
            version=str(eintrag.get("Version") or "").strip() or None,
            hersteller=str(eintrag.get("Hersteller") or "").strip() or None,
            installationspfad=str(eintrag.get("Installationspfad") or "").strip() or None,
        )
        for eintrag in _json_liste(daten.get("Software"))
        if str(eintrag.get("Name") or "").strip()
    ]

    dienste = [
        DienstInfo(
            name=str(eintrag.get("Name") or "").strip(),
            status=str(eintrag.get("Status") or "").strip() or None,
            starttyp=str(eintrag.get("StartType") or "").strip() or None,
        )
        for eintrag in _json_liste(daten.get("Dienste"))
        if str(eintrag.get("Name") or "").strip()
    ]

    firewall_regeln = [
        FirewallRegel(
            name=str(eintrag.get("Name") or "").strip(),
            richtung=str(eintrag.get("Richtung") or "").strip() or "Unbekannt",
            protokoll=str(eintrag.get("Protokoll") or "").strip() or "Any",
            aktion=str(eintrag.get("Aktion") or "").strip() or None,
            port=str(eintrag.get("Port") or "").strip() or None,
            aktiviert=(str(eintrag.get("Aktiviert")).lower() == "true") if eintrag.get("Aktiviert") is not None else None,
        )
        for eintrag in _json_liste(daten.get("FirewallRegeln"))
        if str(eintrag.get("Name") or "").strip()
    ]

    dotnet_versionen = [
        DotNetVersion(
            produkt=str(eintrag.get("Produkt") or "").strip(),
            version=str(eintrag.get("Version") or "").strip(),
            quelle=str(eintrag.get("Quelle") or "").strip() or None,
        )
        for eintrag in _json_liste(daten.get("DotNetVersionen"))
        if str(eintrag.get("Produkt") or "").strip() and str(eintrag.get("Version") or "").strip()
    ]

    sql_instanzen: list[SQLInstanzInfo] = []
    for eintrag in _json_liste(daten.get("SqlInstanzen")):
        instanzname = str(eintrag.get("Instanzname") or "").strip()
        if not instanzname:
            continue

        datenpfade = [
            SQLDatenpfadInfo(
                instanzname=str(pfad.get("Instanzname") or instanzname).strip(),
                kategorie=str(pfad.get("Kategorie") or "Unbekannt").strip(),
                pfad=str(pfad.get("Pfad") or "").strip(),
            )
            for pfad in _json_liste(eintrag.get("Datenpfade"))
            if str(pfad.get("Pfad") or "").strip()
        ]

        sql_instanzen.append(
            SQLInstanzInfo(
                instanzname=instanzname,
                instanz_id=str(eintrag.get("InstanzId") or "").strip() or None,
                version=str(eintrag.get("Version") or "").strip() or None,
                edition=str(eintrag.get("Edition") or "").strip() or None,
                datenpfade=datenpfade,
            )
        )

    eingehend_tcp = [r for r in firewall_regeln if r.richtung.lower() == "inbound" and r.protokoll.upper() == "TCP"]
    eingehend_udp = [r for r in firewall_regeln if r.richtung.lower() == "inbound" and r.protokoll.upper() == "UDP"]
    ausgehend_tcp = [r for r in firewall_regeln if r.richtung.lower() == "outbound" and r.protokoll.upper() == "TCP"]
    ausgehend_udp = [r for r in firewall_regeln if r.richtung.lower() == "outbound" and r.protokoll.upper() == "UDP"]

    return RemoteSystemdaten(
        betriebssystem=BetriebssystemDetails(
            name=str(os_daten.get("Name") or "").strip() or None,
            version=str(os_daten.get("Version") or "").strip() or None,
            build=str(os_daten.get("Build") or "").strip() or None,
            architektur=str(os_daten.get("Architektur") or "").strip() or None,
        ),
        hardware=HardwareDetails(
            cpu_modell=str(hw_daten.get("CpuModell") or "").strip() or None,
            cpu_logische_kerne=int(hw_daten.get("CpuLogischeKerne")) if hw_daten.get("CpuLogischeKerne") is not None else None,
            arbeitsspeicher_gb=float(hw_daten.get("ArbeitsspeicherGB")) if hw_daten.get("ArbeitsspeicherGB") is not None else None,
        ),
        netzwerkidentitaet=Netzwerkidentitaet(
            hostname=str(netz_daten.get("Hostname") or "").strip() or None,
            fqdn=str(netz_daten.get("FQDN") or "").strip() or None,
            domain=str(netz_daten.get("Domain") or "").strip() or None,
            ip_adressen=_normalisiere_liste_ohne_duplikate(str(ip) for ip in netz_daten.get("IPAdressen", []) if str(ip).strip()),
        ),
        cpu_details=CPUDetails(
            physische_kerne=int(cpu_daten.get("PhysischeKerne")) if cpu_daten.get("PhysischeKerne") is not None else None,
            logische_threads=int(cpu_daten.get("LogischeThreads")) if cpu_daten.get("LogischeThreads") is not None else None,
            takt_mhz=float(cpu_daten.get("TaktMHz")) if cpu_daten.get("TaktMHz") is not None else None,
        ),
        dotnet_versionen=dotnet_versionen,
        firewall_regeln=FirewallRegelsatz(
            eingehend_tcp=eingehend_tcp,
            eingehend_udp=eingehend_udp,
            ausgehend_tcp=ausgehend_tcp,
            ausgehend_udp=ausgehend_udp,
        ),
        sage_lizenz=SageLizenzDetails(
            produkt=str(sage_daten.get("Produkt") or "").strip() or None,
            version=str(sage_daten.get("Version") or "").strip() or None,
            build=str(sage_daten.get("Build") or "").strip() or None,
            lizenznehmer=str(sage_daten.get("Lizenznehmer") or "").strip() or None,
            lizenzschluessel=str(sage_daten.get("Lizenzschluessel") or "").strip() or None,
            lizenztyp=str(sage_daten.get("Lizenztyp") or "").strip() or None,
        ),
        dienste=dienste,
        software=software,
        sql_instanzen=sql_instanzen,
    )


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
        netzwerkidentitaet=Netzwerkidentitaet(hostname=socket.gethostname() or None),
        cpu_details=CPUDetails(logische_threads=os.cpu_count()),
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
    ergebnis.netzwerkidentitaet = inventar.netzwerkidentitaet
    ergebnis.cpu_details = inventar.cpu_details
    ergebnis.dotnet_versionen = inventar.dotnet_versionen
    ergebnis.firewall_regeln = inventar.firewall_regeln
    ergebnis.sage_lizenz = inventar.sage_lizenz
    ergebnis.dienste = inventar.dienste
    ergebnis.software = inventar.software

    # Kompatibilitätsfelder für bestehende Reports/CLI.
    ergebnis.betriebssystem = inventar.betriebssystem.name or ergebnis.betriebssystem
    ergebnis.os_version = inventar.betriebssystem.version or ergebnis.os_version
    ergebnis.cpu_logische_kerne = inventar.hardware.cpu_logische_kerne
    ergebnis.cpu_modell = inventar.hardware.cpu_modell
    if inventar.cpu_details.logische_threads is not None:
        ergebnis.cpu_logische_kerne = inventar.cpu_details.logische_threads

    installierte = [
        f"{eintrag.name} {eintrag.version}".strip() if eintrag.version else eintrag.name
        for eintrag in inventar.software
        if eintrag.name
    ]
    ergebnis.installierte_anwendungen = _normalisiere_liste_ohne_duplikate(installierte)
    ergebnis.rollen_details.sql.instanz_details = inventar.sql_instanzen


def _freigegebene_relevante_ports(ergebnis: AnalyseErgebnis) -> list[str]:
    """Formatiert fachlich relevante offene Ports für den Reportabschnitt."""
    relevante = [f"{port.port} ({port.bezeichnung})" for port in ergebnis.ports if port.offen]
    return _normalisiere_liste_ohne_duplikate(relevante)


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
    sql_instanzen = [instanz.instanzname for instanz in ergebnis.rollen_details.sql.instanz_details] or [
        name for name in software_namen if "sql server" in name.lower()
    ]
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
        sql=SQLRollenDetails(
            erkannt=sql_erkannt,
            instanzen=sql_instanzen,
            dienste=sql_dienste,
            instanz_details=ergebnis.rollen_details.sql.instanz_details,
        ),
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
            f"{_HINWEIS_DNS} Hostname konnte nicht aufgelöst werden. Bitte DNS/Netzwerkverbindung prüfen."
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
        ergebnis.netzwerkidentitaet = Netzwerkidentitaet(
            hostname=ergebnis.server,
            fqdn=ergebnis.server if "." in ergebnis.server else None,
            domain=ergebnis.server.split(".", 1)[1] if "." in ergebnis.server else None,
            ip_adressen=ip_adressen,
        )
        ergebnis.hinweise.append(f"Aufgelöste Adressen: {', '.join(ip_adressen)}")

    freigegebene_ports = _freigegebene_relevante_ports(ergebnis)
    if freigegebene_ports:
        ergebnis.hinweise.append("Freigegebene/relevante Ports: " + ", ".join(freigegebene_ports))
    else:
        ergebnis.hinweise.append("Freigegebene/relevante Ports: keine")

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
        try:
            remote_daten = provider.lese_systemdaten(ergebnis.server) if provider.ist_verfuegbar() else None
        except RemoteAbrufFehler as fehler:
            ergebnis.hinweise.append(f"{fehler.kategorie} {fehler.nachricht}")
            remote_daten = None

        if remote_daten is None:
            ergebnis.hinweise.append(
                f"{_HINWEIS_WINRM} Remote-Ziel erkannt: CPU-, Dienst- und Softwaredetails benötigen einen aktiven WinRM/WMI-Adapter."
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


def _validiere_discovery_range(basis: str, start: int, ende: int) -> tuple[str, int, int]:
    """Validiert und normalisiert den Discovery-Adressbereich robust."""
    bereinigte_basis = basis.strip()
    teile = bereinigte_basis.split(".")
    if len(teile) != 3:
        raise ValueError("IPv4-Basis muss genau drei Oktette enthalten (z. B. 192.168.178).")
    if any(not teil.isdigit() or not 0 <= int(teil) <= 255 for teil in teile):
        raise ValueError("IPv4-Basis enthält ungültige Oktette.")
    if not 0 <= start <= 255 or not 0 <= ende <= 255:
        raise ValueError("Start- und Endwert müssen im Bereich 0..255 liegen.")
    return bereinigte_basis, min(start, ende), max(start, ende)


def _ping_host(host: str, timeout: float) -> bool:
    """Prüft ICMP-Erreichbarkeit plattformabhängig über das Ping-Kommando."""
    if timeout <= 0:
        return False
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(max(1, int(timeout * 1000))), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=max(1.0, timeout + 0.5), check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _resolve_forward_dns(host: str) -> str | None:
    """Löst einen Hostnamen via Forward-DNS auf und liefert den kanonischen Namen."""
    try:
        kanonisch, _aliasliste, _adressen = socket.gethostbyname_ex(host)
    except (socket.herror, socket.gaierror, TimeoutError):
        return None
    return kanonisch.strip() or None


def _resolve_reverse_dns(ip_adresse: str) -> str | None:
    """Löst optionalen Reverse-DNS-Namen auf und kapselt Fehler."""
    try:
        hostname, *_ = socket.gethostbyaddr(ip_adresse)
    except (socket.herror, socket.gaierror, TimeoutError):
        return None
    return hostname.strip() or None


def _normalisiere_hostname(hostname: str) -> str:
    """Normalisiert Hostnamen stabil für Vergleich und Deduplizierung.

    Die Normalisierung reduziert FQDN und Kurzname auf denselben Kernwert,
    damit z. B. ``srv-01`` und ``srv-01.domain.local`` zusammengeführt werden.
    """
    bereinigt = hostname.strip().lower().rstrip(".")
    if not bereinigt:
        return ""
    return bereinigt.split(".", maxsplit=1)[0]


def _normalisiere_discovery_hostliste(hosts: Iterable[str]) -> list[str]:
    """Bereinigt und dedupliziert Hostnamen für Discovery-Läufe.

    Die Funktion führt Kurzname/FQDN-Varianten auf einen gemeinsamen Schlüssel
    zusammen. Für die tatsächliche Prüfung wird bevorzugt die FQDN-Variante
    behalten, da sie in heterogenen DNS-Umgebungen robuster auflösbar ist.
    """
    dedupliziert: dict[str, str] = {}
    for rohwert in hosts:
        bereinigt = rohwert.strip().rstrip(".")
        if not bereinigt:
            continue

        normalisiert = bereinigt.lower()
        vergleichsschluessel = _normalisiere_hostname(normalisiert)
        if not vergleichsschluessel:
            continue

        bestehend = dedupliziert.get(vergleichsschluessel)
        if bestehend is None:
            dedupliziert[vergleichsschluessel] = normalisiert
            continue

        # FQDN gewinnt gegenüber Kurzname, damit DNS-Auflösung stabiler bleibt.
        if "." in normalisiert and "." not in bestehend:
            dedupliziert[vergleichsschluessel] = normalisiert

    return sorted(dedupliziert.values())


def _dedupliziere_discovery_ergebnisse(ergebnisse: Iterable[DiscoveryErgebnis]) -> list[DiscoveryErgebnis]:
    """Fasst Discovery-Ergebnisse robust zusammen und entfernt Duplikate."""
    dedupliziert: dict[tuple[str, str], DiscoveryErgebnis] = {}
    for item in sorted(ergebnisse, key=lambda eintrag: (eintrag.hostname.lower(), -eintrag.vertrauensgrad)):
        # Deduplizierung erfolgt über normalisierten Hostnamen + IP,
        # um FQDN-/Kurzname-Varianten robust zusammenzuführen.
        schluessel = (_normalisiere_hostname(item.hostname), item.ip_adresse)
        if schluessel in dedupliziert:
            bestehend = dedupliziert[schluessel]
            bestehend.erkannte_dienste = _normalisiere_liste_ohne_duplikate(bestehend.erkannte_dienste + item.erkannte_dienste)
            bestehend.strategien = _normalisiere_liste_ohne_duplikate(bestehend.strategien + item.strategien)
            bestehend.fehlerursachen = _normalisiere_liste_ohne_duplikate(bestehend.fehlerursachen + item.fehlerursachen)
            bestehend.vertrauensgrad = max(bestehend.vertrauensgrad, item.vertrauensgrad)
            bestehend.erreichbar = bestehend.erreichbar or item.erreichbar
            continue
        dedupliziert[schluessel] = item

    return sorted(dedupliziert.values(), key=lambda item: (item.hostname.lower(), item.ip_adresse))


def _ad_ldap_hinweis() -> str | None:
    """Liefert optionalen AD/LDAP-Hinweis, sofern Domänenumfeld erkannt wird."""
    domain = (os.environ.get("USERDNSDOMAIN") or os.environ.get("USERDOMAIN") or "").strip()
    if domain and domain.lower() not in {"workgroup", "localhost"}:
        return f"Domäne erkannt: {domain}"
    return None


def _ermittle_seed_hosts_via_dns_srv() -> list[str]:
    """Liest optionale Seed-Hosts aus DNS-SRV-Einträgen via nslookup aus."""
    domain = (os.environ.get("USERDNSDOMAIN") or "").strip()
    if not domain or domain.lower() in {"workgroup", "localhost"}:
        return []

    cmd = ["nslookup", "-type=SRV", f"_ldap._tcp.dc._msdcs.{domain}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=4.0, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    # `svr hostname` wird je nach OS/Locale leicht unterschiedlich ausgegeben.
    treffer = re.findall(r"svr hostname\s*=\s*([^\s]+)", result.stdout, flags=re.IGNORECASE)
    return _normalisiere_discovery_hostliste(treffer)


def _ermittle_seed_hosts_via_ad_computer() -> list[str]:
    """Liest optionale Seed-Hosts aus AD-Computerobjekten per PowerShell aus."""
    script = (
        "$ErrorActionPreference='Stop';"
        "if (Get-Module -ListAvailable ActiveDirectory) {"
        "Import-Module ActiveDirectory -ErrorAction Stop;"
        "Get-ADComputer -Filter * -Properties DNSHostName,Name |"
        " Select-Object -First 300 -ExpandProperty DNSHostName"
        "}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8.0,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    return _normalisiere_discovery_hostliste(result.stdout.splitlines())


def ermittle_discovery_seed_hosts(nutze_ad_ldap: bool) -> list[str]:
    """Ermittelt bei Bedarf Seed-Hosts über DNS/AD als optionale Discovery-Quelle."""
    if not nutze_ad_ldap:
        return []

    # DNS-SRV ist leichtgewichtig; AD-Computerobjekte ergänzen die Datenbasis.
    seeds = _ermittle_seed_hosts_via_dns_srv() + _ermittle_seed_hosts_via_ad_computer()
    return _normalisiere_discovery_hostliste(seeds)


def _rollenhinweise_aus_discovery(
    erkannte_dienste: list[str],
    remote_daten: RemoteSystemdaten | None,
) -> list[str]:
    """Leitet Rollenhinweise für Discovery aus Ports, Diensten und Remote-Inventar ab."""
    hinweise: list[str] = []
    erkannte_ports = {int(eintrag) for eintrag in erkannte_dienste if eintrag.isdigit()}

    # Portsignaturen je Rolle zentral auswerten, damit neue Rollenindikatoren
    # künftig an einer Stelle erweitert werden können.
    for rolle, profil in ROLLEN_PORTPROFILE.items():
        rollen_key = rolle.lower()
        rollen_ports = set(profil["ports"])
        if not rollen_ports:
            continue

        for port in sorted(erkannte_ports & rollen_ports):
            hinweise.append(f"{rollen_key}_port_{port}")
        if erkannte_ports & rollen_ports:
            hinweise.append(f"{rollen_key}_portsignatur")

    for dienst in erkannte_dienste:
        if dienst.isdigit():
            continue
        dienstname = dienst.lower()
        for rolle, profil in ROLLEN_PORTPROFILE.items():
            rollen_key = rolle.lower()
            diensthinweise = profil["diensthinweise"]
            if any(token in dienstname for token in diensthinweise):
                hinweise.append(f"{rollen_key}_dienst:{dienstname}")

    if remote_daten is not None:
        if remote_daten.sql_instanzen:
            hinweise.extend(f"sql_instanz:{instanz.instanzname.lower()}" for instanz in remote_daten.sql_instanzen)

        for dienst in remote_daten.dienste:
            dienstname = dienst.name.lower()
            for rolle, profil in ROLLEN_PORTPROFILE.items():
                rollen_key = rolle.lower()
                diensthinweise = profil["diensthinweise"]
                if any(token in dienstname for token in diensthinweise):
                    hinweise.append(f"{rollen_key}_remote_dienst:{dienstname}")

    return _normalisiere_liste_ohne_duplikate(hinweise)


def _entdecke_einzelnen_host(host: str, konfiguration: DiscoveryKonfiguration) -> DiscoveryErgebnis | None:
    """Führt alle Discovery-Strategien für genau einen Host zusammen."""
    strategien: list[str] = []
    fehlerursachen: list[str] = []
    erkannte_dienste: list[str] = []
    aufnahmegruende: list[str] = []
    ip_adresse = host
    erreichbar = False
    vertrauensgrad = 0.0
    namensquelle = "eingabe"

    forward_name = _resolve_forward_dns(host)
    if forward_name:
        strategien.append("forward_dns")
        namensquelle = "forward_dns"
        vertrauensgrad += 0.15

    ip_adressen = _ermittle_ip_adressen(host)
    if ip_adressen:
        ip_adresse = ip_adressen[0]
    else:
        fehlerursachen.append("dns_auflosung")

    # Harte Erreichbarkeit: Der Host antwortet auf ICMP.
    if _ping_host(host, konfiguration.ping_timeout):
        strategien.append("icmp")
        erreichbar = True
        vertrauensgrad += 0.45
        aufnahmegruende.append("harter_check_icmp")

    # Harte Erreichbarkeit: Mindestens ein relevanter TCP-Port antwortet.
    for port in konfiguration.tcp_ports:
        kandidaten = _ermittle_socket_kandidaten(host, port)
        if kandidaten and pruefe_tcp_port(kandidaten, timeout=konfiguration.tcp_timeout):
            erreichbar = True
            strategien.append("tcp_syn")
            erkannte_dienste.append(str(port))

    if erkannte_dienste:
        vertrauensgrad += min(0.4, 0.1 * len(erkannte_dienste))
        aufnahmegruende.append("harter_check_tcp")
    elif "icmp" not in strategien:
        fehlerursachen.append("tcp_timeout")

    hostname = forward_name or host
    # Reverse-DNS liefert ein starkes weiches Signal zur Namensvalidierung.
    reverse_erfolgreich = False
    if konfiguration.nutze_reverse_dns and ip_adressen:
        reverse = _resolve_reverse_dns(ip_adresse)
        if reverse:
            strategien.append("reverse_dns")
            hostname = reverse
            namensquelle = "reverse_dns"
            vertrauensgrad += 0.1
            reverse_erfolgreich = True
        else:
            fehlerursachen.append("reverse_dns_nicht_aufloesbar")

    if not forward_name and namensquelle == "eingabe":
        fehlerursachen.append("forward_dns_nicht_aufloesbar")

    ad_hinweis: str | None = None
    if konfiguration.nutze_ad_ldap:
        ad_hinweis = _ad_ldap_hinweis()
        if ad_hinweis:
            strategien.append("ad_ldap")
            erkannte_dienste.append(ad_hinweis)
            vertrauensgrad += 0.05
        else:
            fehlerursachen.append("ad_ldap_nicht_verfuegbar")

    remote_daten: RemoteSystemdaten | None = None
    provider = KombinierterRemoteProvider()
    if provider.ist_verfuegbar():
        try:
            remote_daten = provider.lese_systemdaten(host)
            if remote_daten is not None:
                strategien.append("remote_inventory")
                vertrauensgrad += 0.35
                aufnahmegruende.append("weiches_signal_remote_inventory")
        except RemoteAbrufFehler:
            fehlerursachen.append("remote_inventory_nicht_verfuegbar")

    # Starkes weiches Signal: Forward-DNS + Reverse-DNS + AD-Hinweis.
    if forward_name and reverse_erfolgreich and ad_hinweis:
        vertrauensgrad += 0.2
        aufnahmegruende.append("weiche_signalkombination_dns_reverse_ad")

    vertrauensgrad = min(1.0, vertrauensgrad)

    # Aufnahmeentscheidung: harte Erreichbarkeit ODER genügend starke weiche Signale.
    if erreichbar:
        if "harter_check_icmp" in aufnahmegruende and "harter_check_tcp" in aufnahmegruende:
            aufnahmegruende.insert(0, "aufnahme_harte_checks_icmp_tcp")
        elif "harter_check_icmp" in aufnahmegruende:
            aufnahmegruende.insert(0, "aufnahme_harter_check_icmp")
        elif "harter_check_tcp" in aufnahmegruende:
            aufnahmegruende.insert(0, "aufnahme_harter_check_tcp")
    elif vertrauensgrad >= konfiguration.min_vertrauensgrad:
        aufnahmegruende.insert(0, "aufnahme_ueber_weiche_signale")
        fehlerursachen.append("nicht_hart_erreichbar_aber_vertrauensschwelle_erreicht")
    else:
        fehlerursachen.append("verworfen_vertrauensgrad_unterschritten")
        return None

    rollenhinweise = _rollenhinweise_aus_discovery(erkannte_dienste, remote_daten)

    return DiscoveryErgebnis(
        hostname=hostname,
        ip_adresse=ip_adresse,
        erreichbar=erreichbar,
        erkannte_dienste=_normalisiere_liste_ohne_duplikate(erkannte_dienste),
        vertrauensgrad=vertrauensgrad,
        strategien=_normalisiere_liste_ohne_duplikate(strategien),
        fehlerursachen=_normalisiere_liste_ohne_duplikate(fehlerursachen),
        aufnahmegrund=";".join(_normalisiere_liste_ohne_duplikate(aufnahmegruende)) if aufnahmegruende else "",
        rollenhinweise=rollenhinweise,
        namensquelle=namensquelle,
    )


def _entdecke_server_von_hostliste(hosts: list[str], conf: DiscoveryKonfiguration) -> list[DiscoveryErgebnis]:
    """Führt Discovery für eine normalisierte Hostliste parallel aus."""
    normalisierte_hosts = _normalisiere_discovery_hostliste(hosts)
    if not normalisierte_hosts:
        return []

    ergebnisse: list[DiscoveryErgebnis] = []
    with ThreadPoolExecutor(max_workers=min(conf.max_worker, len(normalisierte_hosts))) as executor:
        futures = [executor.submit(_entdecke_einzelnen_host, host, conf) for host in normalisierte_hosts]
        for future in as_completed(futures):
            treffer = future.result()
            if treffer is not None:
                ergebnisse.append(treffer)

    return _dedupliziere_discovery_ergebnisse(ergebnisse)


def entdecke_server_mehrere_ranges(
    ranges: list[DiscoveryRangeSegment],
    konfiguration: DiscoveryKonfiguration | None = None,
) -> list[DiscoveryErgebnis]:
    """Ermittelt Discovery-Treffer über mehrere IPv4-Segmente in einem Lauf."""
    conf = konfiguration or DiscoveryKonfiguration()
    hosts: list[str] = []
    range_texte: list[str] = []

    for segment in ranges:
        basis, start, ende = _validiere_discovery_range(segment.basis, segment.start, segment.ende)
        range_texte.append(f"{basis}.{start}-{ende}")
        hosts.extend(f"{basis}.{host_teil}" for host_teil in range(start, ende + 1))

    deduplizierte_ergebnisse = _entdecke_server_von_hostliste(hosts, conf)
    logger.info(
        "Discovery über mehrere Ranges abgeschlossen | Segmente=%s | Kandidaten=%s | Treffer=%s",
        ";".join(range_texte),
        len(_normalisiere_discovery_hostliste(hosts)),
        len(deduplizierte_ergebnisse),
    )
    return deduplizierte_ergebnisse


def entdecke_server_via_seeds(
    seeds: list[str] | None = None,
    konfiguration: DiscoveryKonfiguration | None = None,
) -> list[DiscoveryErgebnis]:
    """Ermittelt Discovery-Treffer über explizite und optionale AD/DNS-Seed-Hosts."""
    conf = konfiguration or DiscoveryKonfiguration()
    manuelle_seeds = _normalisiere_discovery_hostliste(seeds or [])
    auto_seeds = ermittle_discovery_seed_hosts(conf.nutze_ad_ldap)
    kombinierte_seeds = _normalisiere_discovery_hostliste([*manuelle_seeds, *auto_seeds])

    deduplizierte_ergebnisse = _entdecke_server_von_hostliste(kombinierte_seeds, conf)
    logger.info(
        "Discovery via Seeds abgeschlossen | Manuell=%s | Auto(AD/DNS)=%s | Gesamt=%s | Treffer=%s",
        len(manuelle_seeds),
        len(auto_seeds),
        len(kombinierte_seeds),
        len(deduplizierte_ergebnisse),
    )
    return deduplizierte_ergebnisse


def entdecke_server_ergebnisse(
    basis: str,
    start: int,
    ende: int,
    konfiguration: DiscoveryKonfiguration | None = None,
) -> list[DiscoveryErgebnis]:
    """Ermittelt Discovery-Treffer über ein einzelnes Segment (Kompatibilitäts-API)."""
    deduplizierte_ergebnisse = entdecke_server_mehrere_ranges(
        ranges=[DiscoveryRangeSegment(basis=basis, start=start, ende=ende)],
        konfiguration=konfiguration,
    )

    conf = konfiguration or DiscoveryKonfiguration()
    strategie_liste = ["icmp", "tcp_syn"]
    if conf.nutze_reverse_dns:
        strategie_liste.append("reverse_dns")
    if conf.nutze_ad_ldap:
        strategie_liste.append("ad_ldap")

    fehler_counter: dict[str, int] = {}
    for item in deduplizierte_ergebnisse:
        for fehler in item.fehlerursachen:
            fehler_counter[fehler] = fehler_counter.get(fehler, 0) + 1

    normalisierte_basis, normalisierter_start, normalisiertes_ende = _validiere_discovery_range(basis, start, ende)
    laufprotokoll = DiscoveryLaufProtokoll(
        basis=normalisierte_basis,
        start=normalisierter_start,
        ende=normalisiertes_ende,
        strategien=tuple(strategie_liste),
        trefferzahl=len(deduplizierte_ergebnisse),
        fehlerursachen=fehler_counter,
    )
    logger.info(
        "Discovery abgeschlossen | Range=%s.%s-%s | Treffer=%s | Strategien=%s | Fehler=%s",
        laufprotokoll.basis,
        laufprotokoll.start,
        laufprotokoll.ende,
        laufprotokoll.trefferzahl,
        ",".join(laufprotokoll.strategien),
        laufprotokoll.fehlerursachen,
    )

    return deduplizierte_ergebnisse


def entdecke_server_namen(
    hosts: list[str],
    konfiguration: DiscoveryKonfiguration | None = None,
) -> list[DiscoveryErgebnis]:
    """Ermittelt Discovery-Treffer aus einer expliziten Liste von Servernamen."""
    deduplizierte_ergebnisse = entdecke_server_via_seeds(seeds=hosts, konfiguration=konfiguration)
    logger.info(
        "Discovery über Servernamenliste abgeschlossen | Eingaben=%s | Treffer=%s",
        len(hosts),
        len(deduplizierte_ergebnisse),
    )
    return deduplizierte_ergebnisse


def entdecke_server_kandidaten(basis: str, start: int, ende: int) -> list[str]:
    """Kompatibilitätsfunktion: liefert nur Hostnamen aus den Discovery-Ergebnissen."""
    ergebnisse = entdecke_server_ergebnisse(basis=basis, start=start, ende=ende)
    return [treffer.hostname for treffer in ergebnisse]
