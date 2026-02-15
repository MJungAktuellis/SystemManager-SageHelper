"""
server_analysis.py

Modul zur Analyse von Serverrollen und relevanten Informationen.

Funktionen enthalten:
1. Erkennung der Serverrollen (SQL, APP, CTX).
2. Überprüfung der relevanten Ports für Anwendungen wie Sage100.
3. Auslesen relevanter Treiberversionen.
4. Logging aller Ergebnisse für Dokumentationszwecke.
"""

import os
import socket
import logging
import subprocess
from typing import List, Dict

# Logging-Konfiguration
logging.basicConfig(
    filename="logs/server_analysis.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def pruefe_ports(ip_address: str, ports: List[int]) -> Dict[int, str]:
    """
    Prüft, ob die angegebenen Ports auf einem Server offen sind.

    Args:
        ip_address (str): Die Adresse des Servers.
        ports (List[int]): Eine Liste relevanter Ports.

    Returns:
        Dict[int, str]: Ein Dictionary mit Portnummern und Status ('offen' oder 'geschlossen').
    """
    ergebnisse = {}
    for port in ports:
        try:
            with socket.create_connection((ip_address, port), timeout=2):
                ergebnisse[port] = "offen"
        except (socket.timeout, ConnectionRefusedError):
            ergebnisse[port] = "geschlossen"
    return ergebnisse

def serverrolle_erkennen() -> str:
    """
    Ermittelt die Rolle des aktuellen Servers basierend auf installierten Komponenten.

    Returns:
        str: Beschreibung der Serverrolle (z. B. 'SQL', 'APP', 'CTX', 'MIXED', oder 'UNKNOWN').
    """
    rollen = []
    try:
        # SQL-Serverprüfung
        sql_dienste = subprocess.getoutput("sc query | findstr /I MSSQL")
        if sql_dienste:
            rollen.append("SQL")

        # Prüfen auf Applikationsserver
        app_pfade = [
            "C:\\Program Files\\Sage",
            "C:\\Program Files (x86)\\Sage",
            "C:\\Sage"
        ]
        if any(os.path.exists(pfad) for pfad in app_pfade):
            rollen.append("APP")

        # Terminalserver/RDS-Prüfung
        ctx_dienst = subprocess.getoutput("qwinsta")
        if "RDP-Tcp" in ctx_dienst:
            rollen.append("CTX")

        if not rollen:
            return "UNKNOWN"
        return ",".join(rollen)

    except Exception as e:
        logging.error(f"Fehler beim Erkennen der Serverrolle: {e}")
        return "ERROR"

def treiber_versionen_auslesen() -> List[str]:
    """
    Liest die Versionen relevanter Treiber aus (z. B. Netzwerk- und Speichertreiber).

    Returns:
        List[str]: Liste der Treiberinformationen.
    """
    treiber_info = []
    try:
        ergebnis = subprocess.check_output(["driverquery"], shell=True, text=True)
        for line in ergebnis.split("\n"):
            if "Net" in line or "Storage" in line:
                treiber_info.append(line.strip())
    except Exception as e:
        logging.error(f"Fehler beim Auslesen der Treiberversionen: {e}")
    return treiber_info

def analysiere_server():
    """
    Führt eine vollständige Analyse des aktuellen Servers durch: prüft Ports, Serverrolle und Treiberversionen.
    Die Ergebnisse werden geloggt.
    """
    logging.info("Starte Serveranalyse...")

    # Serverrolle erkennen
    rolle = serverrolle_erkennen()
    logging.info(f"Erkannte Serverrolle: {rolle}")

    # Ports prüfen
    relevante_ports = [80, 443, 3389, 1433, 8443]
    ip_address = socket.gethostbyname(socket.gethostname())
    port_ergebnisse = pruefe_ports(ip_address, relevante_ports)
    logging.info(f"Port-Status: {port_ergebnisse}")

    # Treiberversionen auslesen
    treiber = treiber_versionen_auslesen()
    for zeile in treiber:
        logging.info(f"Treiber: {zeile}")

    logging.info("Serveranalyse abgeschlossen.")

if __name__ == "__main__":
    analysiere_server()