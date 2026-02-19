"""Definiert die Update-Strategie inklusive Versionsvergleich und Datenmigration.

Das Modul bündelt bewusst alle Schritte, die bei einem Update vor der eigentlichen
Komponentenausführung passieren müssen:
- installierte Version gegen Zielversion vergleichen,
- persistente Datenbereiche sichern,
- Migrationsablauf nachvollziehbar protokollieren.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
import shutil
from typing import Iterable

from .installation_state import InstallationsPruefung, UNBEKANNTE_VERSION, _ermittle_app_version


@dataclass(slots=True)
class UpdateKontext:
    """Beschreibt den geplanten Installationsmodus mit Versions- und Migrationsstatus."""

    modus: str
    installierte_version: str
    ziel_version: str
    update_erforderlich: bool
    begruendung: str


@dataclass(slots=True)
class MigrationsErgebnis:
    """Ergebnisobjekt für die Datensicherung während eines Updates."""

    durchgefuehrt: bool
    backup_root: Path | None = None
    migrationslog_pfad: Path | None = None
    gesicherte_pfade: list[str] = field(default_factory=list)


def _normalisiere_versionssegmente(version: str) -> list[int | str]:
    """Zerlegt Versionsstrings robust für einen deterministischen Vergleich."""
    segmente: list[int | str] = []
    for token in re.split(r"[.\-+]", version.strip().lower()):
        if not token:
            continue
        if token.isdigit():
            segmente.append(int(token))
        else:
            segmente.append(token)
    return segmente


def _version_ist_neuer(ziel_version: str, installierte_version: str) -> bool:
    """Vergleicht zwei Versionsstrings tolerant und ohne externe Abhängigkeiten."""
    ziel = _normalisiere_versionssegmente(ziel_version)
    installiert = _normalisiere_versionssegmente(installierte_version)

    max_len = max(len(ziel), len(installiert))
    for index in range(max_len):
        ziel_segment = ziel[index] if index < len(ziel) else 0
        installiert_segment = installiert[index] if index < len(installiert) else 0
        if ziel_segment == installiert_segment:
            continue

        if isinstance(ziel_segment, int) and isinstance(installiert_segment, int):
            return ziel_segment > installiert_segment

        return str(ziel_segment) > str(installiert_segment)

    return False


def ermittle_update_kontext(
    pruefung: InstallationsPruefung,
    *,
    ziel_version: str | None = None,
) -> UpdateKontext:
    """Leitet den geeigneten Modus aus Installationszustand und Versionen ab."""
    finale_zielversion = (ziel_version or _ermittle_app_version() or UNBEKANNTE_VERSION).strip()
    installierte_version = (pruefung.erkannte_version or "").strip()

    if not pruefung.installiert:
        return UpdateKontext(
            modus="install",
            installierte_version=installierte_version,
            ziel_version=finale_zielversion,
            update_erforderlich=False,
            begruendung="Neuinstallation erforderlich (kein valider Installationszustand).",
        )

    if not installierte_version or installierte_version == UNBEKANNTE_VERSION:
        return UpdateKontext(
            modus="maintenance",
            installierte_version=installierte_version,
            ziel_version=finale_zielversion,
            update_erforderlich=True,
            begruendung="Installierte Version ist unbekannt – Sicherheitsupdate mit Migration empfohlen.",
        )

    if finale_zielversion != UNBEKANNTE_VERSION and _version_ist_neuer(finale_zielversion, installierte_version):
        return UpdateKontext(
            modus="maintenance",
            installierte_version=installierte_version,
            ziel_version=finale_zielversion,
            update_erforderlich=True,
            begruendung="Neuere Zielversion erkannt, Update inklusive Migrationsschritten erforderlich.",
        )

    return UpdateKontext(
        modus="maintenance",
        installierte_version=installierte_version,
        ziel_version=finale_zielversion,
        update_erforderlich=False,
        begruendung="System ist auf dem aktuellen Stand, Wartung/Integritätsprüfung ausreichend.",
    )


def _kopiere_pfad_quelltreu(quellpfad: Path, zielpfad: Path) -> None:
    """Kopiert Verzeichnisse/Dateien inklusive Metadaten in ein Backupziel."""
    if quellpfad.is_dir():
        shutil.copytree(quellpfad, zielpfad, dirs_exist_ok=True)
        return
    zielpfad.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(quellpfad, zielpfad)


def _iter_report_dateien(root: Path) -> Iterable[Path]:
    """Liefert alle Markdown-Reports aus docs/ für die Datensicherung."""
    docs = root / "docs"
    if not docs.exists():
        return []
    return docs.glob("*.md")


def sichere_persistente_daten_vor_update(
    repo_root: Path,
    *,
    update_kontext: UpdateKontext,
) -> MigrationsErgebnis:
    """Sichert `config/`, `logs/` und Reports bevor ein Update eingespielt wird.

    Auch wenn der eigentliche Installer diese Bereiche nicht gezielt löscht, entsteht
    damit ein expliziter Recovery-Punkt für einen sicheren Updatepfad.
    """
    if not update_kontext.update_erforderlich:
        return MigrationsErgebnis(durchgefuehrt=False)

    zeitstempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = repo_root / "config" / "update_backups" / zeitstempel
    backup_root.mkdir(parents=True, exist_ok=True)

    gesichert: list[str] = []
    for relativ in ("config", "logs"):
        quellpfad = repo_root / relativ
        if not quellpfad.exists():
            continue
        if relativ == "config":
            zielpfad = backup_root / "config"
            shutil.copytree(
                quellpfad,
                zielpfad,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("update_backups"),
            )
        else:
            _kopiere_pfad_quelltreu(quellpfad, backup_root / relativ)
        gesichert.append(relativ)

    reports = list(_iter_report_dateien(repo_root))
    if reports:
        reports_root = backup_root / "reports"
        reports_root.mkdir(parents=True, exist_ok=True)
        for report in reports:
            _kopiere_pfad_quelltreu(report, reports_root / report.name)
        gesichert.append("reports")

    log_pfad = repo_root / "logs" / "update_migration.log"
    log_pfad.parent.mkdir(parents=True, exist_ok=True)
    log_pfad.write_text(
        "\n".join(
            [
                "# Update-Migrationslog",
                f"- Zeitpunkt: {datetime.now().isoformat(timespec='seconds')}",
                f"- Installierte Version: {update_kontext.installierte_version or 'unbekannt'}",
                f"- Zielversion: {update_kontext.ziel_version}",
                f"- Begründung: {update_kontext.begruendung}",
                f"- Backup-Pfad: {backup_root}",
                f"- Gesicherte Bereiche: {', '.join(gesichert) if gesichert else 'keine'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return MigrationsErgebnis(
        durchgefuehrt=True,
        backup_root=backup_root,
        migrationslog_pfad=log_pfad,
        gesicherte_pfade=gesichert,
    )
