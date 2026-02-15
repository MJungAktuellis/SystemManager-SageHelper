"""Datamodelle für Serveranalyse und Dokumentation."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ServerZiel:
    """Beschreibt einen Zielserver mit gewünschter Rollenkennzeichnung."""

    name: str
    rollen: list[str]


@dataclass
class PortStatus:
    """Ergebnis einer Portprüfung."""

    port: int
    offen: bool
    bezeichnung: str


@dataclass
class AnalyseErgebnis:
    """Sammelt alle Informationen zu einem Serverlauf."""

    server: str
    zeitpunkt: datetime
    betriebssystem: str | None = None
    os_version: str | None = None
    rollen: list[str] = field(default_factory=list)
    ports: list[PortStatus] = field(default_factory=list)
    cpu_logische_kerne: int | None = None
    cpu_modell: str | None = None
    installierte_anwendungen: list[str] = field(default_factory=list)
    sage_version: str | None = None
    partner_anwendungen: list[str] = field(default_factory=list)
    management_studio_version: str | None = None
    hinweise: list[str] = field(default_factory=list)
