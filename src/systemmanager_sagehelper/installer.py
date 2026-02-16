"""Kernlogik für den Installationsassistenten.

Dieses Modul kapselt alle Prüf- und Installationsschritte, damit die
CLI-/Script-Einbindung möglichst schlank bleibt.
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

MINDEST_PYTHON_VERSION = (3, 11)
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
STANDARD_REIHENFOLGE = [
    "voraussetzungen",
    "python",
    "pip_venv",
    "abhaengigkeiten",
    "tool_dateien",
]


@dataclass(frozen=True)
class WerkzeugStatus:
    """Beschreibt den ermittelten Status eines benötigten Werkzeugs."""

    name: str
    gefunden: bool
    version: str | None = None


@dataclass(frozen=True)
class InstallationsErgebnis:
    """Repräsentiert das Ergebnis einer Installationskomponente."""

    komponenten_id: str
    name: str
    erfolgreich: bool
    nachricht: str


@dataclass(frozen=True)
class InstallationsKomponente:
    """Definiert eine einzelne, wiederverwendbare Installationskomponente."""

    id: str
    name: str
    default_aktiv: bool
    abhaengigkeiten: tuple[str, ...] = field(default_factory=tuple)
    install_fn: Callable[[], str] = lambda: ""
    verify_fn: Callable[[], tuple[bool, str]] = lambda: (True, "")


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


def hat_adminrechte() -> bool:
    """Prüft, ob der Installer mit administrativen Rechten läuft."""
    if ist_windows_system():
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    if hasattr(os, "geteuid"):
        return os.geteuid() == 0

    return False


def pruefe_voraussetzungen() -> tuple[bool, str]:
    """Validiert grundlegende Systemvoraussetzungen für die Installation."""
    if not ist_windows_system():
        return False, "Dieses Installationsmodell ist auf Windows-Server ausgerichtet."
    if not hat_adminrechte():
        return False, "Der Installer benötigt administrative Rechte."
    return True, "Voraussetzungen (Windows + Adminrechte) erfüllt."


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


def pruefe_pip_und_venv() -> tuple[bool, str]:
    """Prüft, ob pip und venv mit dem aktuellen Interpreter verfügbar sind."""
    pip_status = lese_befehlsausgabe([sys.executable, "-m", "pip", "--version"])
    venv_status = lese_befehlsausgabe([sys.executable, "-m", "venv", "--help"])

    if pip_status and venv_status:
        return True, "pip und venv sind verfügbar."
    return False, "pip oder venv fehlen für den aktiven Python-Interpreter."


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


def richte_tool_dateien_und_launcher_ein(repo_root: Path) -> str:
    """Erstellt einfache Starter-Dateien für Windows und Shell-Umgebungen."""
    script_ordner = repo_root / "scripts"
    script_ordner.mkdir(parents=True, exist_ok=True)

    windows_launcher = script_ordner / "start_systemmanager.bat"
    windows_launcher.write_text(
        "@echo off\r\n"
        "python -m systemmanager_sagehelper %*\r\n",
        encoding="utf-8",
    )

    shell_launcher = script_ordner / "start_systemmanager.sh"
    shell_launcher.write_text(
        "#!/usr/bin/env bash\n"
        "python -m systemmanager_sagehelper \"$@\"\n",
        encoding="utf-8",
    )
    shell_launcher.chmod(0o755)

    return "Launcher-Dateien wurden unter scripts/ eingerichtet."


def erzeuge_installationsbericht() -> list[WerkzeugStatus]:
    """Erzeugt eine kompakte Statusliste für die geführte Ausgabe."""
    return [
        pruefe_werkzeug("git", ["git", "--version"]),
        pruefe_python_version(),
        pruefe_werkzeug("pip", [sys.executable, "-m", "pip", "--version"]),
    ]


def validiere_auswahl_und_abhaengigkeiten(
    komponenten: dict[str, InstallationsKomponente], auswahl: dict[str, bool]
) -> None:
    """Prüft, ob ausgewählte Komponenten eine konsistente Abhängigkeitskette besitzen."""
    unbekannt = [komponenten_id for komponenten_id in auswahl if komponenten_id not in komponenten]
    if unbekannt:
        raise InstallationsFehler(f"Unbekannte Komponenten in Auswahl: {', '.join(unbekannt)}")

    for komponenten_id, aktiv in auswahl.items():
        if not aktiv:
            continue
        for abhaengigkeit in komponenten[komponenten_id].abhaengigkeiten:
            if not auswahl.get(abhaengigkeit, False):
                raise InstallationsFehler(
                    f"Komponente '{komponenten_id}' benötigt '{abhaengigkeit}', "
                    "diese ist jedoch deaktiviert."
                )


def fuehre_installationsplan_aus(
    komponenten: dict[str, InstallationsKomponente],
    auswahl: dict[str, bool],
) -> list[InstallationsErgebnis]:
    """Führt den Installationsplan in fester Reihenfolge mit Verifikation aus."""
    logger = logging.getLogger(__name__)
    validiere_auswahl_und_abhaengigkeiten(komponenten, auswahl)
    ergebnisse: list[InstallationsErgebnis] = []

    for komponenten_id in STANDARD_REIHENFOLGE:
        komponente = komponenten.get(komponenten_id)
        if komponente is None or not auswahl.get(komponenten_id, False):
            continue

        logger.info("Installationsschritt gestartet: %s", komponente.name)
        try:
            install_nachricht = komponente.install_fn()
            erfolgreich, verify_nachricht = komponente.verify_fn()
        except InstallationsFehler:
            raise
        except Exception as exc:
            raise InstallationsFehler(
                f"Komponente '{komponente.name}' wurde unerwartet abgebrochen: {exc}"
            ) from exc

        if not erfolgreich:
            raise InstallationsFehler(
                f"Verifikation fehlgeschlagen für '{komponente.name}': {verify_nachricht}"
            )

        nachricht = f"{install_nachricht} | Verifikation: {verify_nachricht}".strip()
        ergebnis = InstallationsErgebnis(
            komponenten_id=komponente.id,
            name=komponente.name,
            erfolgreich=True,
            nachricht=nachricht,
        )
        ergebnisse.append(ergebnis)
        logger.info("Installationsschritt abgeschlossen: %s", komponente.name)

    return ergebnisse


def schreibe_installationsreport(
    repo_root: Path,
    ergebnisse: list[InstallationsErgebnis],
    auswahl: dict[str, bool],
) -> Path:
    """Schreibt einen konsistenten Installationsbericht im Markdown-Format."""
    report_datei = repo_root / "logs" / "install_report.md"
    report_datei.parent.mkdir(parents=True, exist_ok=True)

    aktive_komponenten = [komponenten_id for komponenten_id, aktiv in auswahl.items() if aktiv]
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    zeilen = [
        "# Installationsreport",
        "",
        f"- **Zeitpunkt:** {zeitstempel}",
        f"- **Python:** {sys.version.split()[0]}",
        f"- **Aktive Komponenten:** {', '.join(aktive_komponenten) if aktive_komponenten else 'keine'}",
        "",
        "## Ergebnis",
        "",
    ]

    for ergebnis in ergebnisse:
        symbol = "✅" if ergebnis.erfolgreich else "❌"
        zeilen.append(f"- {symbol} **{ergebnis.name}** (`{ergebnis.komponenten_id}`): {ergebnis.nachricht}")

    if not ergebnisse:
        zeilen.append("- ⚠️ Es wurde keine Komponente ausgeführt.")

    report_datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    logging.getLogger(__name__).info("Installationsreport geschrieben: %s", report_datei)
    return report_datei


def erstelle_standard_komponenten(repo_root: Path) -> dict[str, InstallationsKomponente]:
    """Erzeugt das zentrale Installationsmodell mit standardisierten Komponenten."""

    def install_voraussetzungen() -> str:
        return "Systemvoraussetzungen geprüft."

    def verify_voraussetzungen() -> tuple[bool, str]:
        return pruefe_voraussetzungen()

    def install_python() -> str:
        installiert = installiere_python_unter_windows()
        if installiert:
            return "Python wurde installiert oder aktualisiert."
        return "Python-Version war bereits ausreichend."

    def verify_python() -> tuple[bool, str]:
        python_status = pruefe_python_version()
        if python_status.gefunden:
            return True, f"Python-Version kompatibel ({python_status.version})."
        return False, f"Python-Version nicht kompatibel ({python_status.version})."

    def install_pip_venv() -> str:
        # ensurepip dient als robuster Fallback für Installationen ohne pip.
        fuehre_installationsbefehl_aus([sys.executable, "-m", "ensurepip", "--upgrade"], "pip-Bootstrap")
        return "pip/venv wurden geprüft und pip ggf. nachinstalliert."

    def install_abhaengigkeiten() -> str:
        installiere_python_pakete(repo_root)
        return "Python-Abhängigkeiten aus requirements.txt verarbeitet."

    komponenten = {
        "voraussetzungen": InstallationsKomponente(
            id="voraussetzungen",
            name="Voraussetzungen prüfen (Adminrechte/OS)",
            default_aktiv=True,
            install_fn=install_voraussetzungen,
            verify_fn=verify_voraussetzungen,
        ),
        "python": InstallationsKomponente(
            id="python",
            name="Python-Version prüfen/aktualisieren",
            default_aktiv=True,
            abhaengigkeiten=("voraussetzungen",),
            install_fn=install_python,
            verify_fn=verify_python,
        ),
        "pip_venv": InstallationsKomponente(
            id="pip_venv",
            name="Pip/venv prüfen",
            default_aktiv=True,
            abhaengigkeiten=("python",),
            install_fn=install_pip_venv,
            verify_fn=pruefe_pip_und_venv,
        ),
        "abhaengigkeiten": InstallationsKomponente(
            id="abhaengigkeiten",
            name="Abhängigkeiten installieren",
            default_aktiv=True,
            abhaengigkeiten=("pip_venv",),
            install_fn=install_abhaengigkeiten,
            verify_fn=lambda: (True, "Abhängigkeiten wurden installiert (oder waren nicht vorhanden)."),
        ),
        "tool_dateien": InstallationsKomponente(
            id="tool_dateien",
            name="Tool-Dateien/Launcher einrichten",
            default_aktiv=True,
            abhaengigkeiten=("abhaengigkeiten",),
            install_fn=lambda: richte_tool_dateien_und_launcher_ein(repo_root),
            verify_fn=lambda: (
                (repo_root / "scripts" / "start_systemmanager.bat").exists()
                and (repo_root / "scripts" / "start_systemmanager.sh").exists(),
                "Launcher-Dateien vorhanden.",
            ),
        ),
    }

    return komponenten
