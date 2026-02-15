"""Verwaltung von SMB-Freigaben für die SystemAG-Struktur.

Die Logik ist zentral im Paket abgelegt und wird nur noch über Legacy-Wrapper
unter ``src/folder_manager.py`` nach außen gespiegelt.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import STANDARD_ORDNER
from .logging_setup import konfiguriere_logger

logger = konfiguriere_logger(__name__, dateiname="folder_manager.log")


@dataclass
class FreigabeErgebnis:
    """Ergebnisobjekt für die Verarbeitung einer einzelnen Freigabe."""

    name: str
    ordner: str
    erfolg: bool
    meldung: str
    principal: str = ""
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


def _logge_prozessdetails(aktion: str, befehl: list[str], ergebnis: subprocess.CompletedProcess[str]) -> None:
    """Schreibt strukturierte Prozessdetails in das Log für bessere Fehleranalyse."""
    logger.info(
        "%s | cmd=%s | rc=%s | stdout=%s | stderr=%s",
        aktion,
        " ".join(befehl),
        ergebnis.returncode,
        ergebnis.stdout.strip(),
        ergebnis.stderr.strip(),
    )


def _ermittle_systemfehlercode(stdout: str, stderr: str) -> int | None:
    """Liest bekannte Windows-Systemfehlercodes aus stdout/stderr aus."""
    kombiniert = f"{stdout}\n{stderr}"
    treffer = re.search(r"Systemfehler\s+(\d+)", kombiniert, re.IGNORECASE)
    return int(treffer.group(1)) if treffer else None


def _freigabe_existiert(freigabename: str) -> bool:
    """Prüft defensiv, ob eine SMB-Freigabe bereits existiert."""
    befehl = ["net", "share", freigabename]
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, check=False)
    _logge_prozessdetails(f"Freigabe-Prüfung {freigabename}", befehl, ergebnis)
    if ergebnis.returncode == 0:
        return True

    # Systemfehler 2310 bedeutet: Freigabe nicht gefunden.
    return _ermittle_systemfehlercode(ergebnis.stdout, ergebnis.stderr) != 2310


def _ermittle_principal_kandidaten() -> list[str]:
    """Ermittelt robuste Principal-Kandidaten mit SID-basiertem Primärweg."""
    kandidaten: list[str] = []
    sid_befehl = [
        "powershell",
        "-NoProfile",
        "-Command",
        "([System.Security.Principal.SecurityIdentifier]'S-1-1-0')."
        "Translate([System.Security.Principal.NTAccount]).Value",
    ]
    sid_ergebnis = subprocess.run(sid_befehl, capture_output=True, text=True, check=False)
    _logge_prozessdetails("Principal-Auflösung via SID", sid_befehl, sid_ergebnis)

    if sid_ergebnis.returncode == 0 and sid_ergebnis.stdout.strip():
        kandidaten.append(sid_ergebnis.stdout.strip())

    # Fallbacks bleiben bewusst lokalisiert, damit Windows-DE/EN robust funktionieren.
    kandidaten.extend(["Everyone", "Jeder", "Authenticated Users"])
    return list(dict.fromkeys(kandidaten))


def _run_share_befehl(befehl: list[str], aktion: str) -> subprocess.CompletedProcess[str]:
    """Zentrale Ausführung mit ``capture_output`` für konsistente Auswertung."""
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, check=False)
    _logge_prozessdetails(aktion, befehl, ergebnis)
    return ergebnis


def erstelle_ordnerstruktur(basis_pfad: str) -> None:
    """Erstellt die gewünschte Ordnerstruktur unterhalb des Basis-Pfades."""
    for rel_path in STANDARD_ORDNER:
        ziel_pfad = Path(basis_pfad) / rel_path
        ziel_pfad.mkdir(parents=True, exist_ok=True)
        logger.info("Ordner erstellt oder vorhanden: %s", ziel_pfad)


def setze_freigaben(basis_pfad: str) -> list[FreigabeErgebnis]:
    """Setzt SMB-Freigaben inkl. robustem Principal-Fallback bei Fehler 1332."""
    freigaben = [
        {"ordner": basis_pfad, "name": "SystemAG$", "rechte": "READ"},
        {"ordner": f"{basis_pfad}/AddinsOL", "name": "AddinsOL$", "rechte": "CHANGE"},
        {"ordner": f"{basis_pfad}/LiveupdateOL", "name": "LiveupdateOL$", "rechte": "CHANGE"},
    ]

    principal_kandidaten = _ermittle_principal_kandidaten()
    ergebnisse: list[FreigabeErgebnis] = []

    for freigabe in freigaben:
        name = freigabe["name"]
        ordner = freigabe["ordner"]
        rechte = freigabe["rechte"]

        if _freigabe_existiert(name):
            loesch_ergebnis = _run_share_befehl(["net", "share", name, "/DELETE"], f"Freigabe löschen {name}")
            if loesch_ergebnis.returncode != 0:
                meldung = f"Vorhandene Freigabe konnte nicht gelöscht werden ({name})."
                ergebnisse.append(
                    FreigabeErgebnis(
                        name=name,
                        ordner=ordner,
                        erfolg=False,
                        meldung=meldung,
                        returncode=loesch_ergebnis.returncode,
                        stdout=loesch_ergebnis.stdout,
                        stderr=loesch_ergebnis.stderr,
                    )
                )
                logger.error(meldung)
                continue

        erstellt = False
        letztes_ergebnis: subprocess.CompletedProcess[str] | None = None
        letzte_meldung = ""

        for principal in principal_kandidaten:
            neu_befehl = [
                "net",
                "share",
                f"{name}={ordner}",
                f"/GRANT:{principal},{rechte}",
                "/REMARK:Automatisch erstellt",
            ]
            neu_ergebnis = _run_share_befehl(neu_befehl, f"Freigabe erstellen {name}")
            letztes_ergebnis = neu_ergebnis

            if neu_ergebnis.returncode == 0:
                meldung = f"Freigabe erfolgreich gesetzt: {name} -> {principal} ({rechte})"
                ergebnisse.append(
                    FreigabeErgebnis(
                        name=name,
                        ordner=ordner,
                        erfolg=True,
                        meldung=meldung,
                        principal=principal,
                        returncode=neu_ergebnis.returncode,
                        stdout=neu_ergebnis.stdout,
                        stderr=neu_ergebnis.stderr,
                    )
                )
                logger.info(meldung)
                erstellt = True
                break

            fehlercode = _ermittle_systemfehlercode(neu_ergebnis.stdout, neu_ergebnis.stderr)
            letzte_meldung = (
                f"Freigabe {name} mit Principal '{principal}' fehlgeschlagen"
                f" (Systemfehler: {fehlercode or 'unbekannt'})."
            )
            if fehlercode == 1332:
                # Komplexe Logik: Nur bei "Konto unbekannt" sinnvoll mit nächster Gruppe weitermachen.
                logger.warning("%s Fallback wird versucht.", letzte_meldung)
                continue
            break

        if not erstellt:
            ergebnisse.append(
                FreigabeErgebnis(
                    name=name,
                    ordner=ordner,
                    erfolg=False,
                    meldung=letzte_meldung or f"Freigabe {name} konnte nicht erstellt werden.",
                    principal=principal_kandidaten[0] if principal_kandidaten else "",
                    returncode=letztes_ergebnis.returncode if letztes_ergebnis else None,
                    stdout=letztes_ergebnis.stdout if letztes_ergebnis else "",
                    stderr=letztes_ergebnis.stderr if letztes_ergebnis else "",
                )
            )
            logger.error(ergebnisse[-1].meldung)

    logger.info("Freigabe-Ergebnisse: %s", [asdict(e) for e in ergebnisse])
    return ergebnisse


def pruefe_und_erstelle_struktur(basis_pfad: str) -> list[FreigabeErgebnis]:
    """Sorgt für vollständige Zielstruktur und setzt anschließend Freigaben."""
    if not Path(basis_pfad).exists():
        logger.info("Basisstruktur nicht vorhanden, wird erstellt: %s", basis_pfad)
    erstelle_ordnerstruktur(basis_pfad)
    return setze_freigaben(basis_pfad)
