"""Optionen für den grafischen und skriptbasierten Installationsablauf.

Dieses Modul kapselt Installationsoptionen zentral, damit GUI, CLI und
Inno-Setup-Integration dieselbe Quelle für Feature-Schalter verwenden.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstallerOptionen:
    """Stellt benutzerseitige Auswahloptionen für den Installer bereit."""

    desktop_icon: bool = False


def mappe_inno_tasks(optionen: InstallerOptionen) -> list[str]:
    """Mappt Installer-Optionen auf Inno-Setup-Tasks.

    Die Task ``desktopicon`` ist im Inno-Skript bereits vorhanden und wird
    ausschließlich bei aktivierter Option übergeben.
    """
    return ["desktopicon"] if optionen.desktop_icon else []


def baue_inno_setup_parameter(optionen: InstallerOptionen) -> list[str]:
    """Erzeugt Inno-CLI-Parameter aus Installer-Optionen.

    - Aktiviert bei Bedarf die Task ``desktopicon``.
    - Deaktiviert die Task explizit, wenn keine Desktop-Verknüpfung gewünscht ist,
      damit stille Installationen deterministisch bleiben.
    """
    tasks = mappe_inno_tasks(optionen)
    if tasks:
        return [f"/TASKS={','.join(tasks)}"]
    return ["/MERGETASKS=!desktopicon"]
