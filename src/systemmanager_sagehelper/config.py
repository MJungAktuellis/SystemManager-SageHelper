"""Zentrale Konfigurationen für Rollen, Ports und Zielordner."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortPruefung:
    """Beschreibt einen fachlich relevanten TCP-Port inklusive Bedeutung."""

    port: int
    bezeichnung: str


STANDARD_PORTS = [
    PortPruefung(port=1433, bezeichnung="Microsoft SQL Server"),
    PortPruefung(port=3389, bezeichnung="RDP / Terminaldienste"),
    PortPruefung(port=135, bezeichnung="RPC Endpoint Mapper"),
]

STANDARD_ORDNER = [
    "AddinsOL/abf",
    "AddinsOL/rewe",
    "Installation/Anpassungen",
    "Installation/AppDesigner",
    "Installation/CD_Ablage",
    "Installation/Lizenzen",
    "Installation/Programmierung",
    "Installation/Update",
    "LiveupdateOL",
    "Dokumentation/Kundenstammblatt",
    "Dokumentation/Logs",
]
