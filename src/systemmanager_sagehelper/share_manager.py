"""Verwaltung von SMB-Freigaben für die SystemAG-Struktur.

Die Logik arbeitet idempotent: Vorhandene Freigaben werden analysiert und nur
bei Bedarf korrigiert. Damit bleibt das Verhalten stabil und vermeidet unnötige
Lösch-/Neuanlagezyklen.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .config import STANDARD_ORDNER
from .logging_setup import konfiguriere_logger
from .share_policy import SharePolicy, ermittle_optionale_ordner

logger = konfiguriere_logger(__name__, dateiname="folder_manager.log")


@dataclass(frozen=True)
class SollFreigabe:
    """Deklariert die gewünschte Zielkonfiguration einer SMB-Freigabe."""

    name: str
    ordner: str
    rechte: str


@dataclass
class FreigabeIstZustand:
    """Erfasst den Ist-Zustand einer Freigabe für Planung und Audit."""

    existiert: bool
    pfad: str = ""
    rechte: dict[str, set[str]] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""


@dataclass
class FreigabeAenderung:
    """Beschreibt eine geplante Änderung zwischen Ist- und Soll-Zustand."""

    soll: SollFreigabe
    ist: FreigabeIstZustand
    aktion: str
    begruendung: str
    diff_text: str


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
    aktion: str = ""
    vorher: dict[str, object] = field(default_factory=dict)
    nachher: dict[str, object] = field(default_factory=dict)


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


def _normalisiere_pfad(pfad: str) -> str:
    """Normalisiert Windows-Pfade für robuste Vergleiche."""
    return str(pfad).replace("/", "\\").rstrip("\\ ").lower()


def _normalisiere_recht(recht: str) -> str:
    """Bringt unterschiedliche Lokalisierungen auf ein kanonisches Rechtslevel."""
    wert = recht.strip().upper().replace("Ä", "AE")
    mapping = {
        "READ": "READ",
        "LESEN": "READ",
        "CHANGE": "CHANGE",
        "AENDERN": "CHANGE",
        "FULL": "FULL",
        "VOLLZUGRIFF": "FULL",
    }
    return mapping.get(wert, wert)


def _normalisiere_principal(principal: str) -> str:
    """Normalisiert Principal-Namen für robuste Vergleiche über Lokalisierungen.

    Hintergrund: ``net share`` kann je nach Systemsprache unterschiedliche Namen
    für die gleiche Gruppe liefern (z. B. ``Everyone``/``Jeder``). Für den
    Soll/Ist-Vergleich wird daher auf ein kanonisches Alias abgebildet.
    """
    bereinigt = principal.strip().lower()
    alias_mapping = {
        "everyone": "everyone",
        "jeder": "everyone",
    }

    # Domänen-/Maschinenpräfixe ausblenden, damit auch "BUILTIN\\Users" oder
    # "DOMAIN\\Jeder" verlässlich erkannt werden.
    kurzname = bereinigt.split("\\")[-1]
    return alias_mapping.get(kurzname, kurzname)


def _rechte_level(recht: str) -> int:
    """Liefert ein ordinales Rechteniveau für Vergleichslogik."""
    return {"READ": 1, "CHANGE": 2, "FULL": 3}.get(_normalisiere_recht(recht), 0)


def _parse_rechte_ausgabe(zeile: str) -> tuple[str, str] | None:
    """Extrahiert Principal und Recht aus einer net-share-Rechtezeile."""
    teile = [teil.strip() for teil in zeile.split(",") if teil.strip()]
    if len(teile) < 2:
        return None
    principal = teile[0]
    recht = _normalisiere_recht(teile[1])
    return principal, recht


def _ermittle_ist_zustand(freigabename: str) -> FreigabeIstZustand:
    """Liest Ist-Zustand einer Freigabe inkl. Pfad und Berechtigungen."""
    befehl = ["net", "share", freigabename]
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, check=False)
    _logge_prozessdetails(f"Freigabe-Prüfung {freigabename}", befehl, ergebnis)

    if ergebnis.returncode != 0:
        if _ermittle_systemfehlercode(ergebnis.stdout, ergebnis.stderr) == 2310:
            return FreigabeIstZustand(existiert=False, stdout=ergebnis.stdout, stderr=ergebnis.stderr)
        # Defensiver Fallback: bei nicht interpretierbaren Fehlern Zustand als vorhanden behandeln.
        return FreigabeIstZustand(existiert=True, stdout=ergebnis.stdout, stderr=ergebnis.stderr)

    pfad = ""
    rechte: dict[str, set[str]] = {}

    for rohzeile in ergebnis.stdout.splitlines():
        zeile = rohzeile.strip()
        if not zeile:
            continue

        pfad_treffer = re.match(r"^(Ressource|Path)\s+(.+)$", zeile, re.IGNORECASE)
        if pfad_treffer:
            pfad = pfad_treffer.group(2).strip()
            continue

        rechte_treffer = re.match(r"^(Berechtigung|Permission)\s+(.+)$", zeile, re.IGNORECASE)
        if rechte_treffer:
            parsed = _parse_rechte_ausgabe(rechte_treffer.group(2))
            if parsed:
                principal, recht = parsed
                rechte.setdefault(principal, set()).add(recht)

    return FreigabeIstZustand(existiert=True, pfad=pfad, rechte=rechte, stdout=ergebnis.stdout, stderr=ergebnis.stderr)


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

    kandidaten.extend(["Everyone", "Jeder", "Authenticated Users"])
    return list(dict.fromkeys(kandidaten))


def _run_share_befehl(befehl: list[str], aktion: str) -> subprocess.CompletedProcess[str]:
    """Zentrale Ausführung mit ``capture_output`` für konsistente Auswertung."""
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, check=False)
    _logge_prozessdetails(aktion, befehl, ergebnis)
    return ergebnis


def _hat_erforderliche_rechte(ist: FreigabeIstZustand, principal_kandidaten: list[str], mindest_recht: str) -> bool:
    """Prüft, ob ein zulässiger Principal bereits ausreichende Rechte besitzt."""
    erforderliches_level = _rechte_level(mindest_recht)
    normalisierte_kandidaten = {_normalisiere_principal(principal) for principal in principal_kandidaten}

    for principal, rechte in ist.rechte.items():
        if _normalisiere_principal(principal) not in normalisierte_kandidaten:
            continue
        for recht in rechte:
            if _rechte_level(recht) >= erforderliches_level:
                return True
    return False


def _formatiere_diff(soll: SollFreigabe, ist: FreigabeIstZustand, aktion: str, begruendung: str) -> str:
    """Erzeugt eine menschenlesbare Diff-Zeile für CLI/GUI-Bestätigung."""
    rechte_ist = ", ".join(f"{p}:{'/'.join(sorted(r))}" for p, r in sorted(ist.rechte.items())) or "(keine)"
    rechte_soll = f"Everyone/Jeder:{_normalisiere_recht(soll.rechte)}"
    ist_pfad = ist.pfad or "(nicht gesetzt)"
    return (
        f"[{aktion.upper()}] {soll.name}\n"
        f"  Begründung : {begruendung}\n"
        f"  Pfad       : {ist_pfad}  ->  {soll.ordner}\n"
        f"  Rechte     : {rechte_ist}  ->  {rechte_soll}\n"
    )


def _kandidat_erklaerung(ist: FreigabeIstZustand, kandidaten_pfade: list[Path]) -> str:
    """Ermittelt einen Hinweis, ob der Ist-Pfad zu einem bekannten Kandidaten passt."""
    if not ist.pfad:
        return ""
    ist_norm = _normalisiere_pfad(ist.pfad)
    for kandidat in kandidaten_pfade:
        if _normalisiere_pfad(str(kandidat)) == ist_norm:
            return f" (gefunden unter Kandidat: {kandidat})"
    return ""


def plane_freigabeaenderungen(
    basis_pfad: str,
    principal_kandidaten: list[str] | None = None,
    kandidaten_pfade: list[Path] | None = None,
) -> list[FreigabeAenderung]:
    """Plant notwendige Share-Anpassungen anhand eines Ist/Soll-Vergleichs."""
    soll_freigaben = [
        SollFreigabe(ordner=basis_pfad, name="SystemAG$", rechte="CHANGE"),
        SollFreigabe(ordner=f"{basis_pfad}/AddinsOL", name="AddinsOL$", rechte="CHANGE"),
        SollFreigabe(ordner=f"{basis_pfad}/LiveupdateOL", name="LiveupdateOL$", rechte="CHANGE"),
    ]

    kandidaten = principal_kandidaten or _ermittle_principal_kandidaten()
    struktur_kandidaten = kandidaten_pfade or []
    plan: list[FreigabeAenderung] = []

    for soll in soll_freigaben:
        ist = _ermittle_ist_zustand(soll.name)
        if not ist.existiert:
            plan.append(
                FreigabeAenderung(
                    soll=soll,
                    ist=ist,
                    aktion="create",
                    begruendung="Freigabe fehlt",
                    diff_text=_formatiere_diff(soll, ist, "create", "Freigabe fehlt"),
                )
            )
            continue

        pfad_ok = _normalisiere_pfad(ist.pfad) == _normalisiere_pfad(soll.ordner)
        rechte_ok = _hat_erforderliche_rechte(ist, kandidaten, soll.rechte)

        if pfad_ok and rechte_ok:
            plan.append(
                FreigabeAenderung(
                    soll=soll,
                    ist=ist,
                    aktion="noop",
                    begruendung="Freigabe bereits konform",
                    diff_text=_formatiere_diff(soll, ist, "noop", "Keine Änderung notwendig"),
                )
            )
            continue

        gruende: list[str] = []
        if not pfad_ok:
            kandidat_text = _kandidat_erklaerung(ist, struktur_kandidaten)
            gruende.append(f"Share-Pfad weicht ab{kandidat_text}")
        if not rechte_ok:
            gruende.append("erforderliche Rechte fehlen")
        begruendung = " und ".join(gruende)
        plan.append(
            FreigabeAenderung(
                soll=soll,
                ist=ist,
                aktion="update",
                begruendung=begruendung,
                diff_text=_formatiere_diff(soll, ist, "update", begruendung),
            )
        )

    return plan


def erstelle_ordnerstruktur(basis_pfad: str, policy: SharePolicy | None = None) -> None:
    """Erstellt die gewünschte Ordnerstruktur unterhalb des Basis-Pfades."""
    for rel_path in STANDARD_ORDNER:
        ziel_pfad = Path(basis_pfad) / rel_path
        ziel_pfad.mkdir(parents=True, exist_ok=True)
        logger.info("Ordner erstellt oder vorhanden: %s", ziel_pfad)

    # Optionale Erweiterung für PowerShell-kompatible Zusatzstruktur.
    for extra_ordner in ermittle_optionale_ordner(basis_pfad, policy):
        extra_ordner.mkdir(parents=True, exist_ok=True)
        logger.info("Policy-Ordner erstellt oder vorhanden: %s", extra_ordner)


def _fuehre_aenderung_aus(aenderung: FreigabeAenderung, principal_kandidaten: list[str]) -> FreigabeErgebnis:
    """Wendet eine geplante Freigabeänderung an und protokolliert Vorher/Nachher."""
    soll = aenderung.soll
    ist_vorher = aenderung.ist

    if aenderung.aktion == "noop":
        meldung = f"Keine Änderung erforderlich: {soll.name}"
        logger.info("%s | vorher=%s", meldung, asdict(ist_vorher))
        return FreigabeErgebnis(
            name=soll.name,
            ordner=soll.ordner,
            erfolg=True,
            meldung=meldung,
            aktion="noop",
            vorher=asdict(ist_vorher),
            nachher=asdict(ist_vorher),
        )

    letztes_ergebnis: subprocess.CompletedProcess[str] | None = None
    letzte_meldung = ""

    for principal in principal_kandidaten:
        befehl = [
            "net",
            "share",
            f"{soll.name}={soll.ordner}",
            f"/GRANT:{principal},{soll.rechte}",
            "/REMARK:Automatisch verwaltet",
        ]
        ergebnis = _run_share_befehl(befehl, f"Freigabe {aenderung.aktion} {soll.name}")
        letztes_ergebnis = ergebnis

        if ergebnis.returncode == 0:
            ist_nachher = _ermittle_ist_zustand(soll.name)
            meldung = (
                f"Freigabe {aenderung.aktion} erfolgreich: {soll.name} -> "
                f"{principal} mit Recht {_normalisiere_recht(soll.rechte)}"
            )
            logger.info(
                "%s | vorher=%s | nachher=%s",
                meldung,
                asdict(ist_vorher),
                asdict(ist_nachher),
            )
            return FreigabeErgebnis(
                name=soll.name,
                ordner=soll.ordner,
                erfolg=True,
                meldung=meldung,
                principal=principal,
                returncode=ergebnis.returncode,
                stdout=ergebnis.stdout,
                stderr=ergebnis.stderr,
                aktion=aenderung.aktion,
                vorher=asdict(ist_vorher),
                nachher=asdict(ist_nachher),
            )

        fehlercode = _ermittle_systemfehlercode(ergebnis.stdout, ergebnis.stderr)
        letzte_meldung = (
            f"Freigabe {soll.name} mit Principal '{principal}' fehlgeschlagen"
            f" (Systemfehler: {fehlercode or 'unbekannt'})."
        )
        if fehlercode == 1332:
            logger.warning("%s Fallback wird versucht.", letzte_meldung)
            continue
        break

    logger.error("%s | vorher=%s", letzte_meldung, asdict(ist_vorher))
    return FreigabeErgebnis(
        name=soll.name,
        ordner=soll.ordner,
        erfolg=False,
        meldung=letzte_meldung or f"Freigabe {soll.name} konnte nicht angepasst werden.",
        principal=principal_kandidaten[0] if principal_kandidaten else "",
        returncode=letztes_ergebnis.returncode if letztes_ergebnis else None,
        stdout=letztes_ergebnis.stdout if letztes_ergebnis else "",
        stderr=letztes_ergebnis.stderr if letztes_ergebnis else "",
        aktion=aenderung.aktion,
        vorher=asdict(ist_vorher),
        nachher={},
    )


def setze_freigaben(
    basis_pfad: str,
    bestaetigung: Callable[[str], bool] | None = None,
) -> list[FreigabeErgebnis]:
    """Setzt SMB-Freigaben idempotent inkl. optionalem Bestätigungsschritt."""
    principal_kandidaten = _ermittle_principal_kandidaten()
    plan = plane_freigabeaenderungen(basis_pfad, principal_kandidaten=principal_kandidaten)

    geaenderte = [eintrag for eintrag in plan if eintrag.aktion != "noop"]
    diff_text = "\n".join(e.diff_text for e in geaenderte) if geaenderte else "Keine Share-Änderungen notwendig."

    if geaenderte and bestaetigung is not None:
        bestaetigt = bestaetigung(diff_text)
        logger.info("Bestätigung für Share-Anpassungen: %s", bestaetigt)
        if not bestaetigt:
            ergebnisse = [
                FreigabeErgebnis(
                    name=e.soll.name,
                    ordner=e.soll.ordner,
                    erfolg=False,
                    meldung="Änderung durch Benutzer abgebrochen.",
                    aktion="abgebrochen",
                    vorher=asdict(e.ist),
                    nachher=asdict(e.ist),
                )
                for e in geaenderte
            ]
            logger.info("Freigabe-Ergebnisse: %s", [asdict(e) for e in ergebnisse])
            return ergebnisse

    ergebnisse = [_fuehre_aenderung_aus(e, principal_kandidaten) for e in plan]
    logger.info("Freigabe-Plan: %s", [asdict(e) for e in plan])
    logger.info("Freigabe-Ergebnisse: %s", [asdict(e) for e in ergebnisse])
    return ergebnisse


def pruefe_und_erstelle_struktur(
    basis_pfad: str,
    bestaetigung: Callable[[str], bool] | None = None,
    policy: SharePolicy | None = None,
) -> list[FreigabeErgebnis]:
    """Sorgt für vollständige Zielstruktur und setzt anschließend Freigaben."""
    if not Path(basis_pfad).exists():
        logger.info("Basisstruktur nicht vorhanden, wird erstellt: %s", basis_pfad)
    erstelle_ordnerstruktur(basis_pfad, policy=policy)
    return setze_freigaben(basis_pfad, bestaetigung=bestaetigung)
