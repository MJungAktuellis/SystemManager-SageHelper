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
from enum import Enum
from pathlib import Path
from typing import Callable, Sequence

MINDEST_PYTHON_VERSION = (3, 11)
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
INSTALLER_ENGINE_LOGDATEI = "install_engine.log"
INSTALLER_REPORT_DATEI = "install_report.md"
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
    status: str = "OK"
    naechste_aktion: str = "Keine Aktion erforderlich."


class ErgebnisStatus(str, Enum):
    """Standardisierte Ergebniszustände für Assistenten und Installer."""

    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class VoraussetzungStatus:
    """Ergebnis einer einzelnen Voraussetzungen-Prüfung inkl. Folgeaktion."""

    pruefung: str
    status: ErgebnisStatus
    nachricht: str
    naechste_aktion: str


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
    return log_ordner / INSTALLER_ENGINE_LOGDATEI


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


def _ist_python_version_kompatibel(version: tuple[int, int, int]) -> bool:
    """Prüft, ob eine geparste Python-Version die Mindestanforderung erfüllt."""
    return version[:2] >= MINDEST_PYTHON_VERSION


def _parse_python_version(versions_text: str | None) -> tuple[int, int, int] | None:
    """Parst die numerische Python-Version aus typischen Versionsausgaben."""
    if not versions_text:
        return None

    for token in versions_text.replace("Python", "").split():
        teile = token.strip().split(".")
        if len(teile) < 2:
            continue
        try:
            major = int(teile[0])
            minor = int(teile[1])
            patch = int(teile[2]) if len(teile) > 2 else 0
            return major, minor, patch
        except ValueError:
            continue
    return None


def _normalisiere_pfad_fuer_vergleich(pfad: str) -> str:
    """Normalisiert Pfade robust für Interpreter-Vergleiche unter Windows/Linux."""
    return os.path.normcase(os.path.abspath(pfad))


def _formatiere_befehl_fuer_logs(befehl: Sequence[str]) -> str:
    """Formatiert einen Befehlsvektor robust für Log- und Statusausgaben."""
    return subprocess.list2cmdline(list(befehl))


def finde_kompatiblen_python_interpreter() -> list[str] | None:
    """Findet einen Python-Interpreter mit Mindestversion in gängigen Quellen."""
    kandidaten = [
        [sys.executable],
        ["py", f"-{MINDEST_PYTHON_VERSION[0]}.{MINDEST_PYTHON_VERSION[1]}"] if ist_windows_system() else None,
        ["py", "-3"] if ist_windows_system() else None,
        ["python"],
        ["python3"],
    ]

    for kandidat in [k for k in kandidaten if k is not None]:
        ausgabe = lese_befehlsausgabe([*kandidat, "--version"])
        version = _parse_python_version(ausgabe)
        if version and _ist_python_version_kompatibel(version):
            return kandidat
    return None


def _pip_verfuegbar_fuer_interpreter(interpreter: Sequence[str]) -> bool:
    """Prüft pip-Verfügbarkeit für einen Interpreter-String inkl. Argumenten."""
    befehl = list(interpreter) + ["-m", "pip", "--version"]
    return lese_befehlsausgabe(befehl) is not None


def starte_installationsassistent_mit_interpreter(interpreter: Sequence[str], argv: list[str] | None = None) -> None:
    """Startet den aktuellen Installer-Prozess mit einem (neuen) Interpreter erneut."""
    script_argv = argv or sys.argv
    cmd = list(interpreter) + script_argv
    logging.getLogger(__name__).info("Starte Re-Entry des Installers: %s", _formatiere_befehl_fuer_logs(cmd))
    raise SystemExit(subprocess.call(cmd))


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


def pruefe_und_behebe_voraussetzungen(argv_reentry: list[str] | None = None) -> list[VoraussetzungStatus]:
    """Prüft Python/Pip und behebt typische Voraussetzungen inkl. Re-Entry.

    Die Funktion liefert standardisierte Zustände (OK/WARN/ERROR) zurück.
    Falls ein neuer Interpreter installiert wurde, wird der Installer automatisch
    mit diesem Interpreter neu gestartet.
    """
    ergebnisse: list[VoraussetzungStatus] = []

    if not ist_windows_system():
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="Betriebssystem",
                status=ErgebnisStatus.ERROR,
                nachricht="Das Installationsmodell unterstützt nur Windows.",
                naechste_aktion="Installer auf einem Windows-Server ausführen.",
            )
        )
        return ergebnisse

    if not hat_adminrechte():
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="Administratorrechte",
                status=ErgebnisStatus.ERROR,
                nachricht="Administratorrechte fehlen.",
                naechste_aktion="Installer als Administrator neu starten.",
            )
        )
        return ergebnisse

    ergebnisse.append(
        VoraussetzungStatus(
            pruefung="Administratorrechte",
            status=ErgebnisStatus.OK,
            nachricht="Administratorrechte vorhanden.",
            naechste_aktion="Keine Aktion erforderlich.",
        )
    )

    interpreter = finde_kompatiblen_python_interpreter()
    if interpreter is None:
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="Python-Version",
                status=ErgebnisStatus.WARN,
                nachricht="Kein kompatibler Python-Interpreter gefunden.",
                naechste_aktion="Python 3.11+ wird über winget/choco installiert.",
            )
        )
        installiere_python_unter_windows()
        interpreter = finde_kompatiblen_python_interpreter()
        if interpreter is None:
            ergebnisse.append(
                VoraussetzungStatus(
                    pruefung="Python-Version",
                    status=ErgebnisStatus.ERROR,
                    nachricht="Python-Installation war nicht erfolgreich.",
                    naechste_aktion="Python manuell installieren und Installer erneut starten.",
                )
            )
            return ergebnisse

    ergebnisse.append(
        VoraussetzungStatus(
            pruefung="Python-Version",
            status=ErgebnisStatus.OK,
            nachricht=f"Kompatibler Interpreter gefunden ({_formatiere_befehl_fuer_logs(interpreter)}).",
            naechste_aktion="Keine Aktion erforderlich.",
        )
    )

    if _normalisiere_pfad_fuer_vergleich(interpreter[0]) != _normalisiere_pfad_fuer_vergleich(sys.executable):
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="Re-Entry",
                status=ErgebnisStatus.WARN,
                nachricht="Installer wird mit dem kompatiblen Interpreter neu gestartet.",
                naechste_aktion=f"Re-Entry mit '{_formatiere_befehl_fuer_logs(interpreter)}'.",
            )
        )
        starte_installationsassistent_mit_interpreter(interpreter, argv=argv_reentry)

    if _pip_verfuegbar_fuer_interpreter([sys.executable]):
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="pip",
                status=ErgebnisStatus.OK,
                nachricht="pip ist funktionsfähig.",
                naechste_aktion="Keine Aktion erforderlich.",
            )
        )
        return ergebnisse

    ergebnisse.append(
        VoraussetzungStatus(
            pruefung="pip",
            status=ErgebnisStatus.WARN,
            nachricht="pip ist nicht verfügbar und wird über ensurepip repariert.",
            naechste_aktion="ensurepip ausführen.",
        )
    )
    fuehre_installationsbefehl_aus([sys.executable, "-m", "ensurepip", "--upgrade"], "pip-Bootstrap")

    if _pip_verfuegbar_fuer_interpreter([sys.executable]):
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="pip",
                status=ErgebnisStatus.OK,
                nachricht="pip wurde erfolgreich bereitgestellt.",
                naechste_aktion="Keine Aktion erforderlich.",
            )
        )
    else:
        ergebnisse.append(
            VoraussetzungStatus(
                pruefung="pip",
                status=ErgebnisStatus.ERROR,
                nachricht="pip konnte nicht bereitgestellt werden.",
                naechste_aktion="Python-Installation prüfen und Installer erneut starten.",
            )
        )

    return ergebnisse


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
    """Erstellt separate Starter für GUI und CLI inkl. Kompatibilitäts-Wrapper."""
    script_ordner = repo_root / "scripts"
    script_ordner.mkdir(parents=True, exist_ok=True)

    gui_launcher = script_ordner / "start_systemmanager_gui.bat"
    gui_launcher.write_text(
        "@echo off\r\n"
        "python src\\gui_manager.py\r\n",
        encoding="utf-8",
    )

    cli_launcher = script_ordner / "start_systemmanager_cli.bat"
    cli_launcher.write_text(
        "@echo off\r\n"
        "python -m systemmanager_sagehelper %*\r\n",
        encoding="utf-8",
    )

    # Kompatibilitäts-Launcher: bietet klare Auswahl und delegiert robust.
    windows_launcher = script_ordner / "start_systemmanager.bat"
    windows_launcher.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "if /I \"%~1\"==\"gui\" goto start_gui\r\n"
        "if /I \"%~1\"==\"cli\" goto start_cli\r\n"
        "echo Bitte Startmodus waehlen:\r\n"
        "echo   - GUI: start_systemmanager.bat gui\r\n"
        "echo   - CLI: start_systemmanager.bat cli [Argumente]\r\n"
        "echo\r\n"
        "echo Starte standardmaessig die GUI ...\r\n"
        "goto start_gui\r\n"
        ":start_gui\r\n"
        "call \"%~dp0start_systemmanager_gui.bat\"\r\n"
        "goto ende\r\n"
        ":start_cli\r\n"
        "shift\r\n"
        "call \"%~dp0start_systemmanager_cli.bat\" %*\r\n"
        ":ende\r\n"
        "endlocal\r\n",
        encoding="utf-8",
    )

    shell_launcher = script_ordner / "start_systemmanager.sh"
    shell_launcher.write_text(
        "#!/usr/bin/env bash\n"
        "python -m systemmanager_sagehelper \"$@\"\n",
        encoding="utf-8",
    )
    shell_launcher.chmod(0o755)

    return "Launcher-Dateien (GUI/CLI + Kompatibilität) wurden unter scripts/ eingerichtet."


def _escape_powershell_literal(text: str) -> str:
    """Escaped einen String für die sichere Verwendung in PowerShell-Literalen."""
    return text.replace("'", "''")


def erstelle_windows_desktop_verknuepfung(
    *,
    ziel_pfad: Path,
    verknuepfungs_name: str = "SystemManager-SageHelper",
    arbeitsverzeichnis: Path | None = None,
) -> Path:
    """Erstellt eine Desktop-Verknüpfung unter Windows via PowerShell/COM.

    Der Pfad wird nach ``%PUBLIC%\\Desktop`` geschrieben, damit die Verknüpfung
    für alle Benutzer verfügbar ist. Fehler werden als ``InstallationsFehler``
    propagiert, damit der Wizard eine präzise Rückmeldung geben kann.
    """
    logger = logging.getLogger(__name__)
    if not ist_windows_system():
        raise InstallationsFehler("Desktop-Verknüpfungen werden nur unter Windows unterstützt.")

    if not ziel_pfad.exists():
        raise InstallationsFehler(f"Shortcut-Ziel existiert nicht: {ziel_pfad}")

    desktop_dir = Path(os.environ.get("PUBLIC", r"C:\\Users\\Public")) / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    shortcut_pfad = desktop_dir / f"{verknuepfungs_name}.lnk"
    ziel_str = _escape_powershell_literal(str(ziel_pfad))
    shortcut_str = _escape_powershell_literal(str(shortcut_pfad))
    workdir = arbeitsverzeichnis or ziel_pfad.parent
    workdir_str = _escape_powershell_literal(str(workdir))

    # COM über WScript.Shell ist auf allen unterstützten Windows-Versionen stabil verfügbar.
    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell;"
        f"$shortcut = $ws.CreateShortcut('{shortcut_str}');"
        f"$shortcut.TargetPath = '{ziel_str}';"
        f"$shortcut.WorkingDirectory = '{workdir_str}';"
        "$shortcut.Save();"
    )

    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = ""
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = (exc.stderr or exc.stdout or "").strip()
        logger.exception("Desktop-Verknüpfung konnte nicht erstellt werden.")
        details = f" Details: {stderr}" if stderr else ""
        raise InstallationsFehler(f"Desktop-Verknüpfung konnte nicht erstellt werden.{details}") from exc

    logger.info("Desktop-Verknüpfung erstellt: %s", shortcut_pfad)
    return shortcut_pfad


def erstelle_desktop_verknuepfung_fuer_python_installation(repo_root: Path) -> Path:
    """Erstellt eine Verknüpfung für den direkten Python-Installationspfad."""
    launcher = repo_root / "scripts" / "start_systemmanager_gui.bat"
    return erstelle_windows_desktop_verknuepfung(
        ziel_pfad=launcher,
        verknuepfungs_name="SystemManager-SageHelper",
        arbeitsverzeichnis=repo_root,
    )


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
            status=ErgebnisStatus.OK.value,
            naechste_aktion="Keine Aktion erforderlich.",
        )
        ergebnisse.append(ergebnis)
        logger.info("Installationsschritt abgeschlossen: %s", komponente.name)

    return ergebnisse


def schreibe_installationsreport(
    repo_root: Path,
    ergebnisse: list[InstallationsErgebnis],
    auswahl: dict[str, bool],
    desktop_verknuepfung_status: str | None = None,
    einstiegspfad: str = "cli",
    optionen: dict[str, str] | None = None,
) -> Path:
    """Schreibt einen konsistenten Installationsbericht im Markdown-Format."""
    report_datei = repo_root / "logs" / INSTALLER_REPORT_DATEI
    report_datei.parent.mkdir(parents=True, exist_ok=True)

    aktive_komponenten = [komponenten_id for komponenten_id, aktiv in auswahl.items() if aktiv]
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    optionen = optionen or {}
    optionen_markdown = "\n".join([f"  - **{name}:** {wert}" for name, wert in optionen.items()])

    zeilen = [
        "# Installationsreport",
        "",
        f"- **Zeitpunkt:** {zeitstempel}",
        f"- **Python:** {sys.version.split()[0]}",
        f"- **Einstiegspfad:** {einstiegspfad.upper()}",
        f"- **Aktive Komponenten:** {', '.join(aktive_komponenten) if aktive_komponenten else 'keine'}",
        "- **Aktive Optionen:**",
        optionen_markdown if optionen_markdown else "  - keine",
        "",
        "## Ergebnis",
        "",
    ]

    for ergebnis in ergebnisse:
        symbol = "✅" if ergebnis.erfolgreich else "❌"
        zeilen.append(f"- {symbol} **{ergebnis.name}** (`{ergebnis.komponenten_id}`): {ergebnis.nachricht}")

    if not ergebnisse:
        zeilen.append("- ⚠️ Es wurde keine Komponente ausgeführt.")

    if desktop_verknuepfung_status:
        # Eigener Abschnitt für die Verknüpfung, damit Supportfälle schneller eingegrenzt werden können.
        zeilen.extend(["", "## Desktop-Verknüpfung", "", f"- {desktop_verknuepfung_status}"])

    report_datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    logging.getLogger(__name__).info("Installationsreport geschrieben: %s", report_datei)
    return report_datei


def erstelle_standard_komponenten(repo_root: Path) -> dict[str, InstallationsKomponente]:
    """Erzeugt das zentrale Installationsmodell mit standardisierten Komponenten."""

    def install_voraussetzungen() -> str:
        statusliste = pruefe_und_behebe_voraussetzungen()
        kritische_fehler = [eintrag for eintrag in statusliste if eintrag.status == ErgebnisStatus.ERROR]
        if kritische_fehler:
            erster = kritische_fehler[0]
            raise InstallationsFehler(f"{erster.pruefung}: {erster.nachricht} | {erster.naechste_aktion}")
        return "Voraussetzungen inkl. Python/Pip wurden geprüft und bei Bedarf behoben."

    def verify_voraussetzungen() -> tuple[bool, str]:
        statusliste = pruefe_und_behebe_voraussetzungen()
        kritische_fehler = [eintrag for eintrag in statusliste if eintrag.status == ErgebnisStatus.ERROR]
        if kritische_fehler:
            erster = kritische_fehler[0]
            return False, f"{erster.pruefung}: {erster.nachricht}"
        return True, "Voraussetzungen sind erfüllt."

    def install_python() -> str:
        return "Python-Status wird in der Voraussetzungsprüfung behandelt."

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
                (repo_root / "scripts" / "start_systemmanager_gui.bat").exists()
                and (repo_root / "scripts" / "start_systemmanager_cli.bat").exists()
                and (repo_root / "scripts" / "start_systemmanager.bat").exists()
                and (repo_root / "scripts" / "start_systemmanager.sh").exists(),
                "Launcher-Dateien vorhanden.",
            ),
        ),
    }

    return komponenten
