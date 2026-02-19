"""Tests für den Ordner-/Freigabeassistenten."""

from __future__ import annotations

from pathlib import Path

from systemmanager_sagehelper.folder_gui import (
    baue_ordnerlauf_protokoll,
    erstelle_abschlussmeldungen,
    erstelle_verstaendlichen_bericht,
)
from systemmanager_sagehelper.share_manager import FreigabeAenderung, FreigabeErgebnis, FreigabeIstZustand, SollFreigabe


def _freigabe(aktion: str, erfolg: bool = True) -> FreigabeErgebnis:
    return FreigabeErgebnis(name="SystemAG$", ordner="C:/SystemAG", erfolg=erfolg, meldung="ok", aktion=aktion)


def test_abschlussmeldungen_zeigen_noop_explizit() -> None:
    meldungen = erstelle_abschlussmeldungen([], [_freigabe("noop")])

    assert "Ordner vorhanden: ja" in meldungen[0]
    assert meldungen[1] == "Freigaben ergänzt: nein."
    assert meldungen[2] == "Keine Aktion nötig: ja."


def test_abschlussmeldungen_zeigen_ergaenzungen_explizit() -> None:
    meldungen = erstelle_abschlussmeldungen([Path("C:/SystemAG/AddinsOL")], [_freigabe("create")])

    assert "fehlende Ordner ergänzt: 1" in meldungen[0]
    assert meldungen[1] == "Freigaben ergänzt: ja."
    assert meldungen[2] == "Keine Aktion nötig: nein."


def test_protokoll_ist_json_sicher_bei_set_werten() -> None:
    plan = [
        FreigabeAenderung(
            soll=SollFreigabe(name="SystemAG$", ordner="C:/SystemAG", rechte="READ"),
            ist=FreigabeIstZustand(existiert=True, pfad="C:/SystemAG", rechte={"Everyone": {"READ"}}),
            aktion="noop",
            begruendung="bereits korrekt",
            diff_text="noop",
        )
    ]

    protokoll = baue_ordnerlauf_protokoll(
        lauf_id="lauf-1",
        zeitstempel="2026-01-01T12:00:00",
        basis_pfad="C:/SystemAG",
        plan=plan,
        ergebnisse=[_freigabe("noop")],
        abschlussmeldungen=["Keine Aktion nötig: ja."],
    )

    assert protokoll["lauf_id"] == "lauf-1"
    assert protokoll["plan"][0]["ist"]["rechte"]["Everyone"] == ["READ"]


def test_verstaendlicher_bericht_enthaelt_alle_abschnitte() -> None:
    plan = [
        FreigabeAenderung(
            soll=SollFreigabe(name="SystemAG$", ordner="C:/SystemAG", rechte="CHANGE"),
            ist=FreigabeIstZustand(existiert=True, pfad="D:/SystemAG", rechte={"Everyone": {"READ"}}),
            aktion="update",
            begruendung="Share-Pfad weicht ab",
            diff_text="[UPDATE] SystemAG$",
        )
    ]

    bericht = erstelle_verstaendlichen_bericht("C:/SystemAG", plan, [Path("C:/SystemAG/LiveupdateOL")])

    assert "Problem:" in bericht
    assert "Auswirkung:" in bericht
    assert "Empfohlene Maßnahme:" in bericht
    assert "Begründung:" in bericht
