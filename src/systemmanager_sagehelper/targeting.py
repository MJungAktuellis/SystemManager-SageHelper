"""Zentrale Zielserver-Logik für CLI und GUI.

Dieses Modul ist die einzige fachliche Quelle für:
- Normalisierung von Servernamen und Rollen
- Parsing von Listen-/Deklarationsparametern
- Aufbau von ``ServerZiel``-Objekten
"""

from __future__ import annotations

from .models import ServerZiel


STANDARD_ROLLE = "APP"


def normalisiere_servernamen(servername: str) -> str:
    """Normalisiert einen Servernamen für konsistente Vergleiche (z. B. Duplikate)."""
    return servername.strip().lower()


def parse_liste(wert: str, *, to_upper: bool = False) -> list[str]:
    """Parst kommaseparierte Werte, entfernt Leereinträge/Duplikate und erhält die Reihenfolge."""
    eintraege: list[str] = []
    for rohwert in wert.split(","):
        kandidat = rohwert.strip()
        if to_upper:
            kandidat = kandidat.upper()
        if kandidat and kandidat not in eintraege:
            eintraege.append(kandidat)
    return eintraege


def parse_deklarationen(wert: str) -> dict[str, list[str]]:
    """Parst Deklarationen im Format ``srv1=SQL,APP;srv2=CTX``."""
    deklarationen: dict[str, list[str]] = {}
    for block in wert.split(";"):
        if "=" not in block:
            continue
        server, rollen = block.split("=", 1)
        server_name = server.strip()
        if not server_name:
            continue
        deklarationen[server_name] = parse_liste(rollen, to_upper=True)
    return deklarationen


def baue_serverziele(servernamen: list[str], deklarationen: dict[str, list[str]], standard_rollen: list[str]) -> list[ServerZiel]:
    """Erzeugt robuste ``ServerZiel``-Objekte aus Namen, Deklarationen und Standardrollen."""
    ziele: list[ServerZiel] = []
    for server in servernamen:
        name = server.strip()
        if not name:
            continue
        rollen = deklarationen.get(name, standard_rollen) or [STANDARD_ROLLE]
        ziele.append(ServerZiel(name=name, rollen=rollen))
    return ziele


def rollen_aus_bool_flags(*, sql: bool, app: bool, ctx: bool, dc: bool = False) -> list[str]:
    """Leitet Rollenliste aus booleschen GUI-Flags ab."""
    rollen: list[str] = []
    if sql:
        rollen.append("SQL")
    if app:
        rollen.append("APP")
    if ctx:
        rollen.append("CTX")
    if dc:
        rollen.append("DC")
    return rollen
