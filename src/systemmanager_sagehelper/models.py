"""Datamodelle für Serveranalyse und Dokumentation."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ServerZiel:
    """Beschreibt einen Zielserver mit gewünschter Rollenkennzeichnung."""

    name: str
    rollen: list[str]
    rollenquelle: str | None = None
    auto_rollen: list[str] = field(default_factory=list)
    manuell_ueberschrieben: bool = False


@dataclass
class PortStatus:
    """Ergebnis einer Portprüfung."""

    port: int
    offen: bool
    bezeichnung: str


@dataclass
class BetriebssystemDetails:
    """Strukturierte Betriebssystemdaten aus lokaler oder Remote-Analyse."""

    name: str | None = None
    version: str | None = None
    build: str | None = None
    architektur: str | None = None


@dataclass
class HardwareDetails:
    """Hardwarebezogene Kerndaten für Kapazitäts- und Plausibilitätsprüfungen."""

    cpu_modell: str | None = None
    cpu_logische_kerne: int | None = None
    arbeitsspeicher_gb: float | None = None


@dataclass
class Kundenstammdaten:
    """Stammdaten eines Kunden für Berichte, GUI und spätere Systemanbindungen."""

    kundenname: str | None = None
    kundennummer: str | None = None
    ansprechpartner: str | None = None
    kontakt_email: str | None = None
    kontakt_telefon: str | None = None


@dataclass
class Netzwerkidentitaet:
    """Eindeutige Netzwerkidentität eines Servers inkl. DNS- und IP-Bezug."""

    hostname: str | None = None
    fqdn: str | None = None
    domain: str | None = None
    ip_adressen: list[str] = field(default_factory=list)


@dataclass
class CPUDetails:
    """Feingranulare CPU-Kennzahlen für Kapazitäts-/Sizing-Auswertungen."""

    physische_kerne: int | None = None
    logische_threads: int | None = None
    takt_mhz: float | None = None


@dataclass
class DotNetVersion:
    """Beschreibt eine konkret installierte .NET-Version mit optionaler Quelle."""

    produkt: str
    version: str
    quelle: str | None = None


@dataclass
class FirewallRegel:
    """Vereinheitlicht eine Firewall-Regel für Reporting und GUI."""

    name: str
    richtung: str
    protokoll: str
    aktion: str | None = None
    port: str | None = None
    aktiviert: bool | None = None


@dataclass
class FirewallRegelsatz:
    """Gruppiert Firewall-Regeln je Richtung/Protokoll für klare Auswertungen."""

    eingehend_tcp: list[FirewallRegel] = field(default_factory=list)
    eingehend_udp: list[FirewallRegel] = field(default_factory=list)
    ausgehend_tcp: list[FirewallRegel] = field(default_factory=list)
    ausgehend_udp: list[FirewallRegel] = field(default_factory=list)


@dataclass
class SageLizenzDetails:
    """Lizenz- und Produktinformationen zu Sage-Installationen."""

    produkt: str | None = None
    version: str | None = None
    build: str | None = None
    lizenznehmer: str | None = None
    lizenzschluessel: str | None = None
    lizenztyp: str | None = None


@dataclass
class DienstInfo:
    """Abbild eines Dienstes (lokal oder remote) für Rollenindikatoren."""

    name: str
    status: str | None = None
    starttyp: str | None = None


@dataclass
class SoftwareInfo:
    """Abbild eines installierten Softwarepakets inkl. optionalem Installationspfad."""

    name: str
    version: str | None = None
    hersteller: str | None = None
    installationspfad: str | None = None


@dataclass
class SQLDatenpfadInfo:
    """Beschreibt einen konkreten SQL-Datenpfad je Instanz und Verwendungszweck."""

    instanzname: str
    kategorie: str
    pfad: str


@dataclass
class SQLInstanzInfo:
    """Erweiterte Metadaten einer SQL-Instanz inkl. erkannter Datenpfade."""

    instanzname: str
    instanz_id: str | None = None
    version: str | None = None
    edition: str | None = None
    datenpfade: list[SQLDatenpfadInfo] = field(default_factory=list)


@dataclass
class SQLRollenDetails:
    """Auswertung der SQL-Rolle auf Basis von Diensten und Instanzhinweisen."""

    erkannt: bool = False
    instanzen: list[str] = field(default_factory=list)
    dienste: list[str] = field(default_factory=list)
    instanz_details: list[SQLInstanzInfo] = field(default_factory=list)


@dataclass
class APPRollenDetails:
    """Auswertung der APP-Rolle auf Basis von Sage-Pfaden und Versionen."""

    erkannt: bool = False
    sage_pfade: list[str] = field(default_factory=list)
    sage_versionen: list[str] = field(default_factory=list)


@dataclass
class CTXRollenDetails:
    """Auswertung der CTX-Rolle mit Session-/Terminaldienst-Indikatoren."""

    erkannt: bool = False
    terminaldienste: list[str] = field(default_factory=list)
    session_indikatoren: list[str] = field(default_factory=list)


@dataclass
class DCRollenDetails:
    """Auswertung der DC-Rolle mit AD- und DNS-typischen Indikatoren."""

    erkannt: bool = False
    ad_dienste: list[str] = field(default_factory=list)
    netzwerk_indikatoren: list[str] = field(default_factory=list)


@dataclass
class RollenDetails:
    """Gruppiert alle strukturierten Rollenauswertungen."""

    sql: SQLRollenDetails = field(default_factory=SQLRollenDetails)
    app: APPRollenDetails = field(default_factory=APPRollenDetails)
    ctx: CTXRollenDetails = field(default_factory=CTXRollenDetails)
    dc: DCRollenDetails = field(default_factory=DCRollenDetails)


@dataclass
class RollenCheckEintrag:
    """Strukturiertes Ergebnis einer Rollenprüfung für UI und Reporting."""

    rolle: str
    erkannt: bool
    details: list[str] = field(default_factory=list)


@dataclass
class PortDienstEintrag:
    """Gemeinsames Datenmodell für Ports und Dienste in Detailkarten."""

    typ: str
    name: str
    status: str
    details: str | None = None


@dataclass
class ServerDetailkarte:
    """Vereinheitlicht strukturierte Detaildaten pro Server für UI/Markdown."""

    server: str
    zeitpunkt: datetime
    rollen: list[str] = field(default_factory=list)
    rollenquelle: str | None = None
    betriebssystem: str | None = None
    os_version: str | None = None
    rollen_checks: list[RollenCheckEintrag] = field(default_factory=list)
    ports_und_dienste: list[PortDienstEintrag] = field(default_factory=list)
    software: list[str] = field(default_factory=list)
    empfehlungen: list[str] = field(default_factory=list)
    freitext_hinweise: list[str] = field(default_factory=list)
    kundenstammdaten: Kundenstammdaten = field(default_factory=Kundenstammdaten)
    netzwerkidentitaet: Netzwerkidentitaet = field(default_factory=Netzwerkidentitaet)
    cpu_details: CPUDetails = field(default_factory=CPUDetails)
    dotnet_versionen: list[DotNetVersion] = field(default_factory=list)
    firewall_regeln: FirewallRegelsatz = field(default_factory=FirewallRegelsatz)
    sage_lizenz: SageLizenzDetails = field(default_factory=SageLizenzDetails)


@dataclass
class DiscoveryErgebnis:
    """Strukturierter Discovery-Treffer mit Qualitäts- und Fehlerhinweisen."""

    hostname: str
    ip_adresse: str
    erreichbar: bool
    erkannte_dienste: list[str] = field(default_factory=list)
    vertrauensgrad: float = 0.0
    strategien: list[str] = field(default_factory=list)
    fehlerursachen: list[str] = field(default_factory=list)
    aufnahmegrund: str | None = None
    rollenhinweise: list[str] = field(default_factory=list)
    namensquelle: str | None = None


@dataclass
class AnalyseErgebnis:
    """Sammelt alle Informationen zu einem Serverlauf."""

    server: str
    zeitpunkt: datetime
    lauf_id: str | None = None
    betriebssystem: str | None = None
    os_version: str | None = None
    rollen: list[str] = field(default_factory=list)
    rollenquelle: str | None = None
    auto_rollen: list[str] = field(default_factory=list)
    manuell_ueberschrieben: bool = False
    manuelle_anmerkung: str = ""
    ports: list[PortStatus] = field(default_factory=list)
    cpu_logische_kerne: int | None = None
    cpu_modell: str | None = None
    installierte_anwendungen: list[str] = field(default_factory=list)
    sage_version: str | None = None
    partner_anwendungen: list[str] = field(default_factory=list)
    management_studio_version: str | None = None
    hinweise: list[str] = field(default_factory=list)
    betriebssystem_details: BetriebssystemDetails = field(default_factory=BetriebssystemDetails)
    hardware_details: HardwareDetails = field(default_factory=HardwareDetails)
    dienste: list[DienstInfo] = field(default_factory=list)
    software: list[SoftwareInfo] = field(default_factory=list)
    rollen_details: RollenDetails = field(default_factory=RollenDetails)
    empfehlungen: list[str] = field(default_factory=list)
    kundenstammdaten: Kundenstammdaten = field(default_factory=Kundenstammdaten)
    netzwerkidentitaet: Netzwerkidentitaet = field(default_factory=Netzwerkidentitaet)
    cpu_details: CPUDetails = field(default_factory=CPUDetails)
    dotnet_versionen: list[DotNetVersion] = field(default_factory=list)
    firewall_regeln: FirewallRegelsatz = field(default_factory=FirewallRegelsatz)
    sage_lizenz: SageLizenzDetails = field(default_factory=SageLizenzDetails)
