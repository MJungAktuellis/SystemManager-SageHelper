"""Tests für den idempotenten Freigabe-Ablauf in ``folder_manager``."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import folder_manager


def _cp(args: list[str], returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    """Erzeugt ein ``CompletedProcess``-Objekt für Mock-Rückgaben."""
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def _net_share_detail(name: str, pfad: str, principal: str, recht: str) -> str:
    """Hilfsausgabe im Stil von ``net share <name>`` für Parser-Tests."""
    return (
        f"Freigabename   {name}\n"
        f"Ressource      {pfad}\n"
        f"Berechtigung   {principal}, {recht}\n"
        "Der Befehl wurde erfolgreich ausgeführt.\n"
    )


def test_setze_freigaben_ohne_aenderungsbedarf_verzichtet_auf_update_befehl() -> None:
    """Wenn Pfad und Rechte passen, darf kein net-share-Update ausgeführt werden."""
    aufrufe: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        aufrufe.append(cmd)

        if cmd[:2] == ["powershell", "-NoProfile"]:
            return _cp(cmd, returncode=0, stdout="Everyone\n")

        if cmd[:2] == ["net", "share"] and len(cmd) == 3:
            name = cmd[2]
            if name == "SystemAG$":
                return _cp(cmd, stdout=_net_share_detail(name, "C:/SystemAG", "Everyone", "READ"))
            if name == "AddinsOL$":
                return _cp(cmd, stdout=_net_share_detail(name, "C:/SystemAG/AddinsOL", "Everyone", "CHANGE"))
            if name == "LiveupdateOL$":
                return _cp(cmd, stdout=_net_share_detail(name, "C:/SystemAG/LiveupdateOL", "Everyone", "CHANGE"))

        if cmd[:2] == ["net", "share"] and len(cmd) >= 5:
            raise AssertionError(f"Unerwarteter Update-Aufruf: {cmd}")

        raise AssertionError(f"Unerwarteter Aufruf: {cmd}")

    with patch("systemmanager_sagehelper.share_manager.subprocess.run", side_effect=fake_run):
        ergebnisse = folder_manager.setze_freigaben("C:/SystemAG")

    assert all(result.erfolg for result in ergebnisse)
    assert all(result.aktion == "noop" for result in ergebnisse)
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
            if "/GRANT:Authenticated Users" in cmd[3]:
                return _cp(cmd, returncode=0, stdout="Der Befehl wurde erfolgreich ausgeführt.\n")

        raise AssertionError(f"Unerwarteter Aufruf: {cmd}")

    with patch("systemmanager_sagehelper.share_manager.subprocess.run", side_effect=fake_run):
        ergebnisse = folder_manager.setze_freigaben("C:/SystemAG")

    assert all(result.erfolg for result in ergebnisse)
    assert all(result.principal == "Jeder" for result in ergebnisse)


def test_setze_freigaben_bricht_nach_bestaetigungsdialog_ab() -> None:
    """Bei explizitem Abbruch dürfen keine Änderungen angewendet werden."""

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["powershell", "-NoProfile"]:
            return _cp(cmd, returncode=0, stdout="Everyone\n")
        if cmd[:2] == ["net", "share"] and len(cmd) == 3:
            return _cp(cmd, returncode=2, stdout="Systemfehler 2310 aufgetreten.\n")
        if cmd[:2] == ["net", "share"] and len(cmd) >= 5:
            raise AssertionError("Es darf kein Schreibzugriff erfolgen, wenn abgebrochen wurde.")
        raise AssertionError(f"Unerwarteter Aufruf: {cmd}")

    with patch("systemmanager_sagehelper.share_manager.subprocess.run", side_effect=fake_run):
        ergebnisse = folder_manager.setze_freigaben("C:/SystemAG", bestaetigung=lambda _: False)

    assert ergebnisse
    assert all(not result.erfolg for result in ergebnisse)
    assert all(result.aktion == "abgebrochen" for result in ergebnisse)
