"""
folder_manager.py

Modul zur Verwaltung und Überprüfung von Ordnerstrukturen auf Servern.

Funktionen enthalten:
1. Erstellung einer vordefinierten Ordnerstruktur.
2. Überprüfung, ob die Struktur existiert, andernfalls Ergänzung.
3. Automatische Setzung von Freigabeberechtigungen.
4. Logging zur Nachvollziehbarkeit aller Änderungen.
"""

from pathlib import Path
import subprocess
import logging
import re
from dataclasses import dataclass, asdict

# Logging-Konfiguration
logging.basicConfig(
    filename="logs/folder_manager.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


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
    logging.info(
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

    # Bewusst lokalisierte Fallbacks, falls SID-Übersetzung nicht verfügbar ist.
    kandidaten.extend(["Everyone", "Jeder", "Authenticated Users"])

    # Reihenfolge behalten, Duplikate entfernen.
    return list(dict.fromkeys(kandidaten))


def _run_share_befehl(befehl: list[str], aktion: str) -> subprocess.CompletedProcess[str]:
    """Zentrale Ausführung mit capture_output für konsistente Auswertung."""
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, check=False)
    _logge_prozessdetails(aktion, befehl, ergebnis)
    return ergebnis



def erstelle_ordnerstruktur(basis_pfad: str):
    """
    Erstellt die Ordnerstruktur unterhalb des Basis-Pfades.

    Args:
        basis_pfad (str): Hauptpfad, in dem die Struktur erstellt werden soll.
    """
    struktur = [
        "AddinsOL/abf",
        "AddinsOL/rewe",
        "Installation/Anpassungen",
        "Installation/AppDesigner",
        "Installation/CD_Ablage",
        "Installation/Lizenzen",
        "Installation/Programmierung",
        "Installation/Update",
        "LiveupdateOL",
        "Dokumentation",
        "Dokumentation/Kundenstammblatt",
        "Dokumentation/Logs"
    ]

    for rel_path in struktur:
        try:
            ziel_pfad = Path(basis_pfad) / rel_path
            ziel_pfad.mkdir(parents=True, exist_ok=True)
            logging.info(f"Ordner erstellt oder vorhanden: {ziel_pfad}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen von {ziel_pfad}: {e}")


def setze_freigaben(basis_pfad: str) -> list[FreigabeErgebnis]:
    """
    Setzt Freigaben für spezifische Ordner innerhalb der Ordnerstruktur.

    Args:
        basis_pfad (str): Hauptpfad der Ordnerstruktur.

    Returns:
        list[FreigabeErgebnis]: Ergebnisliste je Freigabe für GUI/Reporting.
    """
    freigaben = [
        {"ordner": basis_pfad,               "name": "SystemAG$",     "rechte": "READ"},
        {"ordner": f"{basis_pfad}/AddinsOL", "name": "AddinsOL$",     "rechte": "CHANGE"},
        {"ordner": f"{basis_pfad}/LiveupdateOL", "name": "LiveupdateOL$", "rechte": "CHANGE"}
    ]

    principal_kandidaten = _ermittle_principal_kandidaten()
    ergebnisse: list[FreigabeErgebnis] = []

    for freigabe in freigaben:
        name = freigabe["name"]
        ordner = freigabe["ordner"]
        rechte = freigabe["rechte"]

        if _freigabe_existiert(name):
            loesch_befehl = ["net", "share", name, "/DELETE"]
            loesch_ergebnis = _run_share_befehl(loesch_befehl, f"Freigabe löschen {name}")
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
                logging.error(meldung)
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
                logging.info(meldung)
                erstellt = True
                break

            fehlercode = _ermittle_systemfehlercode(neu_ergebnis.stdout, neu_ergebnis.stderr)
            letzte_meldung = (
                f"Freigabe {name} mit Principal '{principal}' fehlgeschlagen"
                f" (Systemfehler: {fehlercode or 'unbekannt'})."
            )

            # 1332 = Konto konnte nicht aufgelöst werden -> kontrollierter Fallback.
            if fehlercode == 1332:
                logging.warning("%s Fallback wird versucht.", letzte_meldung)
                continue

            # Für andere Fehlercode ist kein weiterer Fallback sinnvoll.
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
            logging.error(ergebnisse[-1].meldung)

    logging.info("Freigabe-Ergebnisse: %s", [asdict(e) for e in ergebnisse])
    return ergebnisse


def pruefe_und_erstelle_struktur(basis_pfad: str):
    """
    Prüft, ob die Basisstruktur vorhanden ist, und erstellt sie bei Bedarf.

    Args:
        basis_pfad (str): Der Hauptpfad, an dem die Ordnerstruktur erstellt wird.
    """
    if not Path(basis_pfad).exists():
        logging.info(f"Basisstruktur nicht vorhanden, wird erstellt: {basis_pfad}")
        erstelle_ordnerstruktur(basis_pfad)
    else:
        logging.info(f"Basisstruktur ist bereits vorhanden: {basis_pfad}")
    
    # Freigaben setzen
    setze_freigaben(basis_pfad)

if __name__ == "__main__":
    # Beispielaufruf für Tests
    standard_path = "C:/SystemAG"
    pruefe_und_erstelle_struktur(standard_path)
