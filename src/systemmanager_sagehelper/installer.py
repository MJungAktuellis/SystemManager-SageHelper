"""Kernlogik für den Installationsassistenten.

Dieses Modul kapselt alle Prüf- und Installationsschritte, damit die
CLI-/Script-Einbindung möglichst schlank bleibt.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MINDEST_PYTHON_VERSION = (3, 11)
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


@dataclass(frozen=True)
class WerkzeugStatus:
    """Beschreibt den ermittelten Status eines benötigten Werkzeugs."""

    name: str
    gefunden: bool
    version: str | None = None


class InstallationsFehler(RuntimeError):
    """Signalisiert einen bewusst abgebrochenen Installationsschritt."""


def ermittle_log_datei(repo_root: Path) -> Path:
    """Liefert den Pfad zur Logdatei und stellt den Zielordner sicher bereit."""
    log_ordner = repo_root / "logs"
    log_ordner.mkdir(parents=True, exist_ok=True)
    return log_ordner / "install_assistant.log"


def konfiguriere_logging(repo_root: Path) -> Path:
    """Konfiguriert Dateilogs für den Installer und gibt den Dateipfad zurück."""
    log_datei = ermittle_log_datei(repo_root)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Doppelte Handler vermeiden, falls der Installer mehrfach aus derselben Session läuft.
    vorhandene_datei_handler = [
        handler
        for handler in root_logger.handlers
        if isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_datei
    ]

    if not vorhandene_datei_handler:
        handler = logging.FileHandler(log_datei, encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(handler)

    logging.getLogger(__name__).info("Logging initialisiert: %s", log_datei)
    return log_datei


def ermittle_befehlspfad(name: str) -> str | None:
    """Liefert den absoluten Pfad zu einem ausführbaren Befehl, falls vorhanden."""
    return shutil.which(name)


def lese_befehlsausgabe(befehl: list[str]) -> str | None:
    """Führt einen Kommandozeilenbefehl aus und gibt die erste Zeile der Ausgabe zurück."""
    try:
        ergebnis = subprocess.run(
            befehl,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        logging.getLogger(__name__).warning("Versionsabfrage fehlgeschlagen: %s", befehl)
        return None

    ausgabe = (ergebnis.stdout or ergebnis.stderr).strip()
    if not ausgabe:
        return None
    return ausgabe.splitlines()[0].strip()


def pruefe_werkzeug(name: str, versionsbefehl: list[str]) -> WerkzeugStatus:
    """Prüft, ob ein Werkzeug vorhanden ist und liest optional dessen Version."""
    pfad = ermittle_befehlspfad(name)
    if pfad is None:
        return WerkzeugStatus(name=name, gefunden=False)

    version = lese_befehlsausgabe(versionsbefehl)
    return WerkzeugStatus(name=name, gefunden=True, version=version)


def ist_windows_system() -> bool:
    """Kennzeichnet, ob die Installation auf einem Windows-System läuft."""
    return sys.platform.startswith("win")


def pruefe_python_version() -> WerkzeugStatus:
    """Ermittelt den Status der aktuell laufenden Python-Version."""
    version = sys.version.split()[0]
    gefunden = sys.version_info >= MINDEST_PYTHON_VERSION
    return WerkzeugStatus(name="python", gefunden=gefunden, version=version)


def ist_kommando_verfuegbar(name: str) -> bool:
    """Prüft knapp, ob ein Kommando im PATH verfügbar ist."""
    return ermittle_befehlspfad(name) is not None


def fuehre_installationsbefehl_aus(befehl: list[str], beschreibung: str) -> None:
    """Führt einen Installationsbefehl aus und wirft bei Fehlern eine Fachausnahme."""
    logging.getLogger(__name__).info("Starte: %s", " ".join(befehl))
    try:
        subprocess.check_call(befehl)
    except (OSError, subprocess.CalledProcessError) as exc:
        logging.getLogger(__name__).exception("Fehlgeschlagen: %s", beschreibung)
        raise InstallationsFehler(f"{beschreibung} fehlgeschlagen: {' '.join(befehl)}") from exc


def installiere_git_unter_windows() -> bool:
    """Installiert Git unter Windows automatisiert via winget/choco (falls möglich)."""
    if ist_kommando_verfuegbar("git"):
        logging.getLogger(__name__).info("Git bereits vorhanden.")
        return False

    if ist_kommando_verfuegbar("winget"):
        fuehre_installationsbefehl_aus(
            [
                "winget",
                "install",
                "--id",
                "Git.Git",
                "--exact",
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--silent",
            ],
            "Git-Installation über winget",
        )
        return True

    if ist_kommando_verfuegbar("choco"):
        fuehre_installationsbefehl_aus(
            ["choco", "install", "git", "-y"],
            "Git-Installation über Chocolatey",
        )
        return True

    raise InstallationsFehler(
        "Git ist nicht installiert und weder winget noch choco wurden gefunden."
    )


def installiere_python_unter_windows() -> bool:
    """Installiert Python 3.11+ unter Windows, wenn keine passende Version verfügbar ist."""
    if pruefe_python_version().gefunden:
        logging.getLogger(__name__).info("Python-Version ist bereits ausreichend.")
        return False

    if ist_kommando_verfuegbar("winget"):
        fuehre_installationsbefehl_aus(
            [
                "winget",
                "install",
                "--id",
                "Python.Python.3.11",
                "--exact",
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--silent",
            ],
            "Python-Installation über winget",
        )
        return True

    if ist_kommando_verfuegbar("choco"):
        fuehre_installationsbefehl_aus(
            ["choco", "install", "python", "-y"],
            "Python-Installation über Chocolatey",
        )
        return True

    raise InstallationsFehler(
        "Python 3.11+ fehlt und weder winget noch choco wurden gefunden."
    )


def installiere_python_pakete(repo_root: Path, python_executable: str | None = None) -> None:
    """Installiert Paketanforderungen aus requirements.txt im Ziel-Repository."""
    req_datei = repo_root / "requirements.txt"
    if not req_datei.exists():
        logging.getLogger(__name__).info("Keine requirements.txt gefunden: %s", req_datei)
        return

    interpreter = python_executable or sys.executable
    fuehre_installationsbefehl_aus(
        [interpreter, "-m", "pip", "install", "-r", str(req_datei)],
        "Installation der Python-Abhängigkeiten",
    )


def erzeuge_installationsbericht() -> list[WerkzeugStatus]:
    """Erzeugt eine kompakte Statusliste für die geführte Ausgabe."""
    return [
        pruefe_werkzeug("git", ["git", "--version"]),
        pruefe_python_version(),
        pruefe_werkzeug("pip", [sys.executable, "-m", "pip", "--version"]),
    ]
