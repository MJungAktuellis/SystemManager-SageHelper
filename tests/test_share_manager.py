"""Gezielte Tests für Soll/Ist-Abgleich und Meldungstexte im Share-Management."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from systemmanager_sagehelper import share_manager
from systemmanager_sagehelper.share_manager import FreigabeIstZustand


def test_plan_verwendet_fuer_systemag_das_sollrecht_change() -> None:
    """Die Soll-Definition für ``SystemAG$`` muss auf ``CHANGE`` stehen."""

    def fake_istzustand(name: str) -> FreigabeIstZustand:
        return FreigabeIstZustand(existiert=False, stdout=f"Systemfehler 2310: {name}")

    with patch("systemmanager_sagehelper.share_manager._ermittle_ist_zustand", side_effect=fake_istzustand):
        plan = share_manager.plane_freigabeaenderungen("C:/SystemAG", principal_kandidaten=["Everyone"])

    systemag_eintrag = next(eintrag for eintrag in plan if eintrag.soll.name == "SystemAG$")
    assert systemag_eintrag.soll.rechte == "CHANGE"
    assert "Everyone/Jeder:CHANGE" in systemag_eintrag.diff_text


def test_plan_akzeptiert_lokalisierte_principalnamen_im_istzustand() -> None:
    """Ein bestehendes ``Jeder``-Recht muss als gültiges Äquivalent zu ``Everyone`` gelten."""
    istzustand = {
        "SystemAG$": FreigabeIstZustand(existiert=True, pfad="C:/SystemAG", rechte={"Jeder": {"CHANGE"}}),
        "AddinsOL$": FreigabeIstZustand(existiert=True, pfad="C:/SystemAG/AddinsOL", rechte={"Everyone": {"CHANGE"}}),
        "LiveupdateOL$": FreigabeIstZustand(
            existiert=True,
            pfad="C:/SystemAG/LiveupdateOL",
            rechte={"Everyone": {"CHANGE"}},
        ),
    }

    with patch("systemmanager_sagehelper.share_manager._ermittle_ist_zustand", side_effect=lambda name: istzustand[name]):
        plan = share_manager.plane_freigabeaenderungen("C:/SystemAG", principal_kandidaten=["Everyone"])

    systemag_eintrag = next(eintrag for eintrag in plan if eintrag.soll.name == "SystemAG$")
    assert systemag_eintrag.aktion == "noop"


def test_plan_markiert_bestehende_dollarfreigaben_mit_zu_niedrigem_recht_als_update() -> None:
    """Bereits vorhandene ``$``-Freigaben mit nur ``READ`` müssen als Update geplant werden."""
    istzustand = {
        "SystemAG$": FreigabeIstZustand(existiert=True, pfad="C:/SystemAG", rechte={"Everyone": {"READ"}}),
        "AddinsOL$": FreigabeIstZustand(existiert=True, pfad="C:/SystemAG/AddinsOL", rechte={"Everyone": {"READ"}}),
        "LiveupdateOL$": FreigabeIstZustand(
            existiert=True,
            pfad="C:/SystemAG/LiveupdateOL",
            rechte={"Everyone": {"READ"}},
        ),
    }

    with patch("systemmanager_sagehelper.share_manager._ermittle_ist_zustand", side_effect=lambda name: istzustand[name]):
        plan = share_manager.plane_freigabeaenderungen("C:/SystemAG", principal_kandidaten=["Everyone"])

    assert all(eintrag.aktion == "update" for eintrag in plan)
    assert all("erforderliche Rechte fehlen" in eintrag.begruendung for eintrag in plan)
    assert all("Everyone/Jeder:CHANGE" in eintrag.diff_text for eintrag in plan)


def test_erfolgsmeldung_beschreibt_recht_verstaendlich() -> None:
    """Die Abschlussmeldung soll Principal und gesetztes Recht klar benennen."""
    aenderung = share_manager.FreigabeAenderung(
        soll=share_manager.SollFreigabe(name="SystemAG$", ordner="C:/SystemAG", rechte="CHANGE"),
        ist=FreigabeIstZustand(existiert=False),
        aktion="create",
        begruendung="Freigabe fehlt",
        diff_text="",
    )

    def fake_run(_befehl: list[str], _aktion: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["net", "share"], returncode=0, stdout="ok", stderr="")

    ist_nachher = FreigabeIstZustand(existiert=True, pfad="C:/SystemAG", rechte={"Everyone": {"CHANGE"}})

    with (
        patch("systemmanager_sagehelper.share_manager._run_share_befehl", side_effect=fake_run),
        patch("systemmanager_sagehelper.share_manager._ermittle_ist_zustand", return_value=ist_nachher),
    ):
        ergebnis = share_manager._fuehre_aenderung_aus(aenderung, principal_kandidaten=["Everyone"])

    assert ergebnis.erfolg is True
    assert "Everyone mit Recht CHANGE" in ergebnis.meldung


def test_plan_kennzeichnet_kandidatenpfad_in_begruendung() -> None:
    """Bei Pfadabweichung soll der erkannte Kandidatenpfad im Grund auftauchen."""
    istzustand = {
        "SystemAG$": FreigabeIstZustand(existiert=True, pfad="D:/Kunde/SystemAG", rechte={"Everyone": {"CHANGE"}}),
        "AddinsOL$": FreigabeIstZustand(existiert=True, pfad="C:/SystemAG/AddinsOL", rechte={"Everyone": {"CHANGE"}}),
        "LiveupdateOL$": FreigabeIstZustand(existiert=True, pfad="C:/SystemAG/LiveupdateOL", rechte={"Everyone": {"CHANGE"}}),
    }

    with patch("systemmanager_sagehelper.share_manager._ermittle_ist_zustand", side_effect=lambda name: istzustand[name]):
        plan = share_manager.plane_freigabeaenderungen(
            "C:/SystemAG",
            principal_kandidaten=["Everyone"],
            kandidaten_pfade=[Path("D:/Kunde/SystemAG")],
        )

    systemag_eintrag = next(eintrag for eintrag in plan if eintrag.soll.name == "SystemAG$")
    assert systemag_eintrag.aktion == "update"
    assert "gefunden unter Kandidat" in systemag_eintrag.begruendung
