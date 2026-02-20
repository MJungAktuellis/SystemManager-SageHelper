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

# Discovery prüft bewusst mehr Ports als die kompakte Standardanalyse,
# damit Rollenkandidaten (SQL/APP/CTX) frühzeitig aus Netzwerksignaturen
# abgeleitet werden können.
DISCOVERY_TCP_PORTS: tuple[int, ...] = (
    53,
    80,
    88,
    135,
    139,
    389,
    443,
    445,
    464,
    636,
    1433,
    1434,
    3268,
    3269,
    3389,
    4022,
    8080,
    8443,
)

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
