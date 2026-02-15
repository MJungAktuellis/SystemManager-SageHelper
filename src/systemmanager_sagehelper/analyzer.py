"""Analysefunktionen für lokale oder remote erreichbare Windows-Server."""

from __future__ import annotations

import platform
import socket
from datetime import datetime

from .config import STANDARD_PORTS
from .models import AnalyseErgebnis, PortStatus, ServerZiel


def pruefe_tcp_port(host: str, port: int, timeout: float = 0.8) -> bool:
    """Prüft effizient per Socket, ob ein TCP-Port erreichbar ist."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def analysiere_server(ziel: ServerZiel) -> AnalyseErgebnis:
    """Erstellt ein Basis-Analyseergebnis mit Portstatus und Systemhinweisen."""
    ergebnis = AnalyseErgebnis(
        server=ziel.name,
        zeitpunkt=datetime.now(),
        rollen=ziel.rollen,
        betriebssystem=platform.system(),
        os_version=platform.version(),
    )

    for port_info in STANDARD_PORTS:
        offen = pruefe_tcp_port(ziel.name, port_info.port)
        ergebnis.ports.append(
            PortStatus(port=port_info.port, offen=offen, bezeichnung=port_info.bezeichnung)
        )

    if platform.system().lower() != "windows":
        ergebnis.hinweise.append(
            "Analyse läuft nicht auf Windows; WMI/PowerShell-Details sind daher nicht aktiv."
        )

    return ergebnis
