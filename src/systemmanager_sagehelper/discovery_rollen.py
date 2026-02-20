"""Gemeinsame Heuristiken zur Rollenableitung aus Discovery-Treffern."""

from __future__ import annotations

from collections.abc import Iterable


def ableite_rollen_aus_discoveryindikatoren(
    *,
    erkannte_dienste: Iterable[str],
    rollenhinweise: Iterable[str],
    erreichbar: bool,
) -> list[str]:
    """Leitet Rollen über gewichtete Discovery-Indikatoren konsistent ab.

    Die Funktion wird bewusst von mehreren UI-Pfaden genutzt, damit
    Onboarding und Serveranalyse dieselben Regeln für SQL/APP/CTX/DC anwenden.
    """

    punktestand = {"SQL": 0, "APP": 0, "CTX": 0, "DC": 0}

    # Port-/Dienstgewichtung: SQL bleibt auch ohne offenen 1433 möglich.
    erkannte_porttokens = {token.strip() for token in erkannte_dienste if token.strip().isdigit()}
    if erkannte_porttokens & {"1433", "1434", "4022"}:
        punktestand["SQL"] += 4
    if "3389" in erkannte_porttokens:
        punktestand["CTX"] += 4
    if erkannte_porttokens & {"53", "88", "389", "445", "464", "636", "3268", "3269"}:
        punktestand["DC"] += 4

    # Analysevorbefunde aus Discovery (z. B. Remote-Inventar, SQL-Dienste, Instanzen).
    for hinweis in rollenhinweise:
        lower = hinweis.lower()
        if lower.startswith("sql_"):
            punktestand["SQL"] += 3
        if lower.startswith("dc_"):
            punktestand["DC"] += 3
        if "termservice" in lower or "sessionenv" in lower:
            punktestand["CTX"] += 2
        if any(token in lower for token in ("netlogon", "kdc", "ldap", "kerberos", "dns")):
            punktestand["DC"] += 2

    # Restliche erreichbare Systeme werden als APP gewichtet, aber nicht blind bevorzugt.
    if erreichbar:
        punktestand["APP"] += 1

    rollen = [rolle for rolle, score in punktestand.items() if score >= 3]
    if not rollen:
        # Fallback mit höchstem Score statt starrem APP-Default.
        beste_rolle = max(punktestand, key=punktestand.get)
        rollen = [beste_rolle]
    return rollen


def formatiere_erreichbarkeitsstatus(*, erreichbar: bool, vertrauensgrad: float) -> str:
    """Liefert eine einheitliche Statusdarstellung für Discovery-Zeilen."""

    erreichbarkeitsstatus = "erreichbar" if erreichbar else "nicht erreichbar"
    if vertrauensgrad >= 0.8:
        vertrauensklasse = "hoch"
    elif vertrauensgrad >= 0.5:
        vertrauensklasse = "mittel"
    else:
        vertrauensklasse = "niedrig"
    return f"{erreichbarkeitsstatus} ({vertrauensklasse})"
