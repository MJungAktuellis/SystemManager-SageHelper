"""Zentrale Installationsprüfung inkl. Marker-, Versions- und Integritätsvalidierung.

Dieses Modul ist bewusst unabhängig von GUI-Frameworks gehalten, damit es sowohl
im Launcher als auch in direkten CLI-/Modul-Einstiegen wiederverwendet werden kann.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

PRODUKTNAME = "SystemManager-SageHelper"
INSTALLATIONS_SCHEMA_VERSION = 1
UNBEKANNTE_VERSION = "0.0.0+unbekannt"

KRITISCHE_DATEIEN = (
    "scripts/install.py",
    "src/gui_manager.py",
    "src/server_analysis_gui.py",
    "src/folder_manager.py",
    "src/doc_generator.py",
    "src/systemmanager_sagehelper/__init__.py",
)


@dataclass(slots=True)
class InstallationsPruefung:
    """Ergebnisobjekt für die Installationsvalidierung."""

    installiert: bool
    gruende: list[str] = field(default_factory=list)
    marker_pfad: Path | None = None
    erkannte_version: str | None = None



def _repo_root() -> Path:
    """Ermittelt das Repository-Root relativ zu diesem Modul."""
    return Path(__file__).resolve().parents[2]



def _programmdata_basis() -> Path:
    """Liefert den ProgramData-Pfad (mit robustem Fallback für Nicht-Windows-Systeme)."""
    rohwert = os.environ.get("ProgramData")
    if rohwert:
        return Path(rohwert)
    return Path.home() / ".programdata"



def installations_marker_pfad() -> Path:
    """Berechnet den stabilen Marker-Pfad in `%ProgramData%` für Installationsstatus."""
    return _programmdata_basis() / PRODUKTNAME / "config" / "installation_state.json"



def _sha256_fuer_datei(datei: Path) -> str:
    """Berechnet den SHA-256-Hash einer Datei in Streaming-Manier."""
    hasher = hashlib.sha256()
    with datei.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()



def _ermittle_app_version() -> str:
    """Ermittelt die aktuelle App-Version mit bestmöglichem Fallback."""
    try:
        from importlib.metadata import version

        return version("systemmanager-sagehelper")
    except Exception:
        return os.environ.get("SYSTEMMANAGER_APP_VERSION", UNBEKANNTE_VERSION)



def schreibe_installations_marker(
    *,
    repo_root: Path | None = None,
    version: str | None = None,
    kritische_dateien: tuple[str, ...] = KRITISCHE_DATEIEN,
) -> Path:
    """Schreibt einen Marker mit Version und Integritätsdaten für kritische Dateien."""
    root = repo_root or _repo_root()
    marker_pfad = installations_marker_pfad()
    marker_pfad.parent.mkdir(parents=True, exist_ok=True)

    datei_hashes: dict[str, dict[str, str | int]] = {}
    for relativ in kritische_dateien:
        datei = root / relativ
        if not datei.exists():
            continue
        datei_hashes[relativ] = {
            "sha256": _sha256_fuer_datei(datei),
            "size": datei.stat().st_size,
        }

    payload = {
        "schema_version": INSTALLATIONS_SCHEMA_VERSION,
        "produkt": PRODUKTNAME,
        "version": version or _ermittle_app_version(),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "critical_files": datei_hashes,
    }
    marker_pfad.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return marker_pfad



def pruefe_installationszustand(
    *,
    erwartete_version: str | None = None,
    repo_root: Path | None = None,
) -> InstallationsPruefung:
    """Prüft Marker, Versionskonsistenz und Dateiintegrität in einem zentralen Schritt."""
    marker_pfad = installations_marker_pfad()
    root = repo_root or _repo_root()
    gruende: list[str] = []

    if not marker_pfad.exists():
        return InstallationsPruefung(
            installiert=False,
            gruende=[f"Installationsmarker fehlt: {marker_pfad}"],
            marker_pfad=marker_pfad,
        )

    try:
        marker = json.loads(marker_pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return InstallationsPruefung(
            installiert=False,
            gruende=[f"Installationsmarker ist ungültig oder nicht lesbar: {exc}"],
            marker_pfad=marker_pfad,
        )

    if marker.get("schema_version") != INSTALLATIONS_SCHEMA_VERSION:
        gruende.append("Installationsmarker hat eine inkompatible Schema-Version.")

    erkannte_version = str(marker.get("version") or "").strip() or None
    ziel_version = erwartete_version or _ermittle_app_version()
    if not erkannte_version:
        gruende.append("Installationsmarker enthält keine Versionsinformation.")
    elif ziel_version != UNBEKANNTE_VERSION and erkannte_version != ziel_version:
        gruende.append(
            f"Installierte Version ({erkannte_version}) passt nicht zur erwarteten Version ({ziel_version})."
        )

    gespeicherte_dateien = marker.get("critical_files") or {}
    if not gespeicherte_dateien:
        gruende.append("Installationsmarker enthält keine Integritätsdaten für kritische Dateien.")

    for relativ, integritaet in gespeicherte_dateien.items():
        datei = root / relativ
        if not datei.exists():
            gruende.append(f"Kritische Datei fehlt: {relativ}")
            continue

        erwarteter_hash = str(integritaet.get("sha256") or "")
        erwartete_groesse = int(integritaet.get("size") or 0)
        aktuelle_groesse = datei.stat().st_size
        if erwartete_groesse and aktuelle_groesse != erwartete_groesse:
            gruende.append(f"Dateigröße abweichend: {relativ}")
            continue

        aktueller_hash = _sha256_fuer_datei(datei)
        if erwarteter_hash and aktueller_hash != erwarteter_hash:
            gruende.append(f"Dateiintegrität verletzt: {relativ}")

    return InstallationsPruefung(
        installiert=not gruende,
        gruende=gruende,
        marker_pfad=marker_pfad,
        erkannte_version=erkannte_version,
    )



def install_workflow_befehl() -> list[str]:
    """Liefert den kanonischen Installations-Workflow-Befehl für alle Launcher."""
    return [sys.executable, "scripts/install.py"]



def fuehre_installation_aus() -> int:
    """Startet den zentralen Installationsworkflow synchron und gibt den Exitcode zurück."""
    befehl = install_workflow_befehl()
    return subprocess.call(befehl)



def verarbeite_installations_guard(
    pruefung: InstallationsPruefung,
    *,
    modulname: str,
    fehlermeldung_fn: Callable[[str], None],
    installationsfrage_fn: Callable[[str], bool],
    installation_starten_fn: Callable[[], int] = fuehre_installation_aus,
) -> bool:
    """Einheitlicher Guard für blockierte Module mit Aktion „Installation starten".

    Rückgabe ``True`` bedeutet: Modul darf starten.
    Rückgabe ``False`` bedeutet: Modul bleibt gesperrt.
    """
    if pruefung.installiert:
        return True

    gruende = "\n- " + "\n- ".join(pruefung.gruende) if pruefung.gruende else ""
    fehlermeldung_fn(
        f"{modulname} ist noch nicht vollständig installiert.{gruende}\n\n"
        "Bitte starten Sie zuerst den Installationsworkflow."
    )

    if installationsfrage_fn("Installation starten?"):
        return installation_starten_fn() == 0
    return False
