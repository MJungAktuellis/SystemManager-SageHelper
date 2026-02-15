"""Tests für den defensiven Freigabe-Ablauf in ``folder_manager``."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import folder_manager


def _cp(args: list[str], returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    """Erzeugt ein ``CompletedProcess``-Objekt für Mock-Rückgaben."""
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_setze_freigaben_loescht_nicht_bei_2310() -> None:
    """Wenn Freigaben nicht existieren (2310), darf kein Delete ausgeführt werden."""

    aufrufe: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        aufrufe.append(cmd)

        if cmd[:2] == ["powershell", "-NoProfile"]:
            return _cp(cmd, returncode=0, stdout="Everyone\n")

        if cmd[:2] == ["net", "share"] and len(cmd) == 3:
            return _cp(cmd, returncode=2, stdout="Systemfehler 2310 aufgetreten.\n")

        if cmd[:2] == ["net", "share"] and len(cmd) >= 5:
            return _cp(cmd, returncode=0, stdout="Der Befehl wurde erfolgreich ausgeführt.\n")

        raise AssertionError(f"Unerwarteter Aufruf: {cmd}")

    with patch("folder_manager.subprocess.run", side_effect=fake_run):
        ergebnisse = folder_manager.setze_freigaben("C:/SystemAG")

    assert all(result.erfolg for result in ergebnisse)
    assert not any("/DELETE" in cmd for cmd in aufrufe)


def test_setze_freigaben_faellt_bei_1332_auf_alternativen_principal_zurueck() -> None:
    """Bei Fehler 1332 soll die nächste Gruppe kontrolliert probiert werden."""

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["powershell", "-NoProfile"]:
            return _cp(cmd, returncode=0, stdout="Everyone\n")

        if cmd[:2] == ["net", "share"] and len(cmd) == 3:
            return _cp(cmd, returncode=2, stdout="Systemfehler 2310 aufgetreten.\n")

        if cmd[:2] == ["net", "share"] and len(cmd) >= 5:
            if "/GRANT:Everyone" in cmd[3]:
                return _cp(cmd, returncode=2, stdout="Systemfehler 1332 aufgetreten.\n")
            if "/GRANT:Jeder" in cmd[3]:
                return _cp(cmd, returncode=0, stdout="Der Befehl wurde erfolgreich ausgeführt.\n")

        raise AssertionError(f"Unerwarteter Aufruf: {cmd}")

    with patch("folder_manager.subprocess.run", side_effect=fake_run):
        ergebnisse = folder_manager.setze_freigaben("C:/SystemAG")

    assert all(result.erfolg for result in ergebnisse)
    assert all(result.principal == "Jeder" for result in ergebnisse)
