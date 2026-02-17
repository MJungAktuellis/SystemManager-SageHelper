"""Geführter Installationsassistent für SystemManager-SageHelper.

Dieses Skript bietet einen interaktiven Auswahlmodus für Installationskomponenten
und führt die Installation in einer festen, validierten Reihenfolge aus.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from systemmanager_sagehelper.gui_state import GUIStateStore, erstelle_installer_modulzustand
from systemmanager_sagehelper.installation_state import _ermittle_app_version, schreibe_installations_marker
from systemmanager_sagehelper.installer import (
    ErgebnisStatus,
    InstallationsFehler,
    STANDARD_REIHENFOLGE,
    erstelle_standard_komponenten,
    erzeuge_installationsbericht,
    fuehre_installationsplan_aus,
    konfiguriere_logging,
    pruefe_und_behebe_voraussetzungen,
    schreibe_installationsreport,
    validiere_auswahl_und_abhaengigkeiten,
    erstelle_desktop_verknuepfung_fuer_python_installation,
)

LOGGER = logging.getLogger(__name__)

STATUS_PREFIX = {
    ErgebnisStatus.OK: "[OK]",
    ErgebnisStatus.WARN: "[WARN]",
    ErgebnisStatus.ERROR: "[ERROR]",
}


def _safe_print(text: str) -> None:
    """Gibt Text robust auf der Konsole aus, auch bei limitierter Windows-Codepage.

    Hintergrund: Auf älteren Windows-Terminals ist `sys.stdout.encoding` häufig keine
    UTF-8-Variante (z. B. cp1252). Unicode-Sonderzeichen können dort zu
    `UnicodeEncodeError` führen. Deshalb normalisieren wir die Ausgabe vorab in die
    Zielkodierung und ersetzen nicht darstellbare Zeichen zuverlässig.

    Fallback-Verhalten: Sollte trotz Vorverarbeitung ein Kodierungsfehler auftreten,
    wird der Text in eine sichere ASCII-Ausgabe umgewandelt, damit die Installation
    niemals wegen einer Konsolenausgabe abbricht.
    """
    ziel_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        ausgabe_text = text.encode(ziel_encoding, errors="replace").decode(ziel_encoding)
        print(ausgabe_text)
    except UnicodeEncodeError:
        ascii_fallback = text.encode("ascii", errors="replace").decode("ascii")
        print(ascii_fallback)


def drucke_voraussetzungsstatus() -> None:
    """Zeigt standardisierte Zustände der Voraussetzungskontrolle an."""
    _safe_print("\nVoraussetzungen:")
    for status in pruefe_und_behebe_voraussetzungen():
        prefix = STATUS_PREFIX[status.status]
        _safe_print(f"  {prefix} [{status.status.value}] {status.pruefung}: {status.nachricht}")
        if status.naechste_aktion and status.naechste_aktion != "Keine Aktion erforderlich.":
            _safe_print(f"      [INFO] Nächste Aktion: {status.naechste_aktion}")


def drucke_statusbericht() -> None:
    """Zeigt den aktuellen Installationsstatus in kompakter Form an."""
    _safe_print("\nSystemprüfung:")
    for status in erzeuge_installationsbericht():
        prefix = "[OK]" if status.gefunden else "[ERROR]"
        version = f" ({status.version})" if status.version else ""
        _safe_print(f"  {prefix} {status.name}{version}")


def _frage_ja_nein(prompt: str, standard: bool = True) -> bool:
    """Fragt eine Ja/Nein-Entscheidung mit sinnvoller Standardauswahl ab."""
    suffix = "[J/n]" if standard else "[j/N]"
    try:
        eingabe = input(f"{prompt} {suffix}: ").strip().lower()
    except EOFError:
        # Fallback für nicht-interaktive Umgebungen (z. B. One-Click-Launcher mit Umleitung).
        _safe_print("[WARN] Keine Benutzereingabe möglich, Standardwert wird verwendet.")
        return standard

    if not eingabe:
        return standard
    if eingabe in {"j", "ja", "y", "yes"}:
        return True
    if eingabe in {"n", "nein", "no"}:
        return False

    _safe_print("[WARN] Ungültige Eingabe, Standardwert wird übernommen.")
    return standard


def ermittle_interaktive_auswahl(komponenten: dict) -> dict[str, bool]:
    """Ermittelt die gewünschte Komponentenauswahl interaktiv am Terminal."""
    _safe_print("\nInteraktiver Modus: Komponenten können optional deaktiviert werden.")
    _safe_print("Standardmäßig sind alle Komponenten aktiviert.\n")

    auswahl = {komponenten_id: komponenten[komponenten_id].default_aktiv for komponenten_id in STANDARD_REIHENFOLGE}

    for komponenten_id in STANDARD_REIHENFOLGE:
        komponente = komponenten[komponenten_id]
        aktiv = _frage_ja_nein(f"Komponente aktivieren: {komponente.name}", standard=komponente.default_aktiv)
        auswahl[komponenten_id] = aktiv

    validiere_auswahl_und_abhaengigkeiten(komponenten, auswahl)
    return auswahl


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parst Installer-Argumente für interaktive und One-Click-Ausführung."""
    parser = argparse.ArgumentParser(description="Installationsassistent für SystemManager-SageHelper")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Aktiviert alle Standard-Komponenten ohne Eingabeaufforderung.",
    )
    desktop_icon_group = parser.add_mutually_exclusive_group()
    desktop_icon_group.add_argument(
        "--desktop-icon",
        dest="desktop_icon",
        action="store_true",
        default=True,
        help="Erstellt nach erfolgreicher Installation eine Desktop-Verknüpfung (Standard).",
    )
    desktop_icon_group.add_argument(
        "--no-desktop-icon",
        dest="desktop_icon",
        action="store_false",
        help="Unterdrückt die Erstellung einer Desktop-Verknüpfung nach der Installation.",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Startpunkt des geführten Installationsprozesses."""
    cli_args = parse_cli_args()
    _safe_print("=== Installation von SystemManager-SageHelper ===")
    log_datei = konfiguriere_logging(REPO_ROOT)
    _safe_print(f"[INFO] Installationslog: {log_datei}")
    LOGGER.info("Installationslauf gestartet.")

    komponenten = erstelle_standard_komponenten(REPO_ROOT)

    try:
        drucke_voraussetzungsstatus()
        drucke_statusbericht()
        if cli_args.non_interactive:
            # One-Click-Modus: alle Standardkomponenten laut Default aktivieren.
            auswahl = {
                komponenten_id: komponenten[komponenten_id].default_aktiv
                for komponenten_id in STANDARD_REIHENFOLGE
            }
            validiere_auswahl_und_abhaengigkeiten(komponenten, auswahl)
            _safe_print("\n[INFO] Non-Interactive-Modus aktiv: Standardauswahl wird verwendet.")
        else:
            auswahl = ermittle_interaktive_auswahl(komponenten)
        ergebnisse = fuehre_installationsplan_aus(komponenten, auswahl)

        desktop_verknuepfung_status = "Desktop-Verknüpfung: Deaktiviert"
        desktop_verknuepfung_pfad: Path | None = None
        if cli_args.desktop_icon:
            try:
                desktop_verknuepfung_pfad = erstelle_desktop_verknuepfung_fuer_python_installation(REPO_ROOT)
                desktop_verknuepfung_status = f"Desktop-Verknüpfung: Erfolgreich erstellt ({desktop_verknuepfung_pfad})"
                LOGGER.info("Desktop-Verknüpfung erfolgreich erstellt: %s", desktop_verknuepfung_pfad)
            except InstallationsFehler as exc:
                desktop_verknuepfung_status = f"Desktop-Verknüpfung: Fehler ({exc})"
                LOGGER.warning("Desktop-Verknüpfung konnte nicht erstellt werden: %s", exc)
        else:
            LOGGER.info("Desktop-Verknüpfung wurde per CLI-Option deaktiviert.")

        report_datei = schreibe_installationsreport(
            REPO_ROOT,
            ergebnisse,
            auswahl,
            desktop_verknuepfung_status=desktop_verknuepfung_status,
        )
        marker_datei = schreibe_installations_marker(repo_root=REPO_ROOT)

        # Persistiert den Installer-Status zusätzlich im GUI-State, damit Launcher
        # und weitere Oberflächen den Zustand ohne Marker-Details auswerten können.
        GUIStateStore().speichere_modulzustand(
            "installer",
            erstelle_installer_modulzustand(
                installiert=True,
                version=_ermittle_app_version(),
                bericht_pfad=str(report_datei),
            ),
        )
    except InstallationsFehler as fehler:
        LOGGER.error("Installationsfehler: %s", fehler)
        _safe_print(f"[ERROR] {fehler}")
        _safe_print(f"[INFO] Details im Log: {log_datei}")
        raise SystemExit(1) from fehler
    except Exception:
        LOGGER.exception("Unerwarteter Fehler während der Installation.")
        _safe_print("[ERROR] Unerwarteter Fehler während der Installation.")
        _safe_print(f"[INFO] Details im Log: {log_datei}")
        raise SystemExit(1)

    LOGGER.info("Installationslauf erfolgreich abgeschlossen.")
    _safe_print("\n[OK] Installation abgeschlossen.")
    _safe_print(f"[INFO] Logdatei: {log_datei}")
    _safe_print(f"[INFO] Installationsreport: {report_datei}")
    _safe_print(f"[INFO] Installationsmarker: {marker_datei}")
    if cli_args.desktop_icon:
        if desktop_verknuepfung_pfad:
            _safe_print(f"[INFO] Desktop-Verknüpfung: {desktop_verknuepfung_pfad}")
        else:
            _safe_print("[WARN] Desktop-Verknüpfung konnte nicht erstellt werden. Details siehe Installationsreport.")
    else:
        _safe_print("[INFO] Desktop-Verknüpfung wurde deaktiviert.")
    _safe_print("Startbeispiel:")
    _safe_print("  python -m systemmanager_sagehelper scan --server localhost --rollen APP --out report.md")


if __name__ == "__main__":
    main()
