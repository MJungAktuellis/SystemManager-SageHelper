"""GUI-Wizard für Ordner- und Freigabeverwaltung.

Der Wizard führt Anwender durch einen klaren Ablauf:
1) Zielordner auswählen oder automatisch finden
2) Soll/Ist-Vergleich prüfen
3) Änderungen bestätigen und anwenden
4) Ergebnis strukturiert mit Lauf-ID/Zeitstempel speichern
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .config import STANDARD_ORDNER
from .folder_structure import (
    StrukturKandidat,
    ermittle_fehlende_ordner,
    finde_systemag_kandidaten,
    pruefe_systemag_kandidaten,
)
from .gui_state import GUIStateStore
from .installation_state import pruefe_installationszustand, verarbeite_installations_guard
from .logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from .share_manager import FreigabeAenderung, FreigabeErgebnis, plane_freigabeaenderungen, pruefe_und_erstelle_struktur

logger = konfiguriere_logger(__name__, dateiname="folder_gui.log")


class FolderWizardGUI:
    """Geführter Assistent für Ordner-/Freigabekonfiguration."""

    def __init__(self, master: tk.Misc | None = None, *, state_store: GUIStateStore | None = None) -> None:
        self.state_store = state_store or GUIStateStore()
        self.modulzustand = self.state_store.lade_modulzustand("folder_manager")

        self.window = tk.Toplevel(master) if master is not None else tk.Tk()
        self.window.title("Ordner- und Freigabeassistent")
        self.window.geometry("980x700")

        self._zielordner_var = tk.StringVar(value=self._initialer_zielordner())
        self._status_var = tk.StringVar(value="Bereit: Zielordner prüfen und Analyse laden.")
        self._plan: list[FreigabeAenderung] = []
        self._kandidatenanalyse: list[StrukturKandidat] = []
        self._aktion_laeuft = False
        self._letzter_lauf_erfolgreich = False

        self._schliessen_button: ttk.Button | None = None
        self._abbrechen_button: ttk.Button | None = None

        self.window.protocol("WM_DELETE_WINDOW", self._beende_assistent)

        self._baue_layout()

    def _initialer_zielordner(self) -> str:
        """Priorisiert den zuletzt bestätigten Zielpfad vor älteren Fallbacks."""
        gespeicherte_pfade = self.modulzustand.get("ausgabepfade", {})
        if not isinstance(gespeicherte_pfade, dict):
            return str(Path.home() / "SystemAG")

        bestaetigt = gespeicherte_pfade.get("bestaetigter_zielpfad")
        basis = gespeicherte_pfade.get("basis_pfad")
        return str(bestaetigt or basis or Path.home() / "SystemAG")

    def _baue_layout(self) -> None:
        haupt = ttk.Frame(self.window, padding=16)
        haupt.pack(fill="both", expand=True)

        ttk.Label(haupt, text="Ordner- und Freigabeverwaltung", style="Headline.TLabel").pack(anchor="w")
        ttk.Label(
            haupt,
            text=(
                "Ablauf: Zielordner wählen → Bestand prüfen → Änderungen bestätigen → Abschluss auswerten."
            ),
        ).pack(anchor="w", pady=(4, 12))

        pfad_rahmen = ttk.LabelFrame(haupt, text="1) Zielordner für SystemAG", padding=10)
        pfad_rahmen.pack(fill="x")
        ttk.Entry(pfad_rahmen, textvariable=self._zielordner_var, width=90).pack(side="left", fill="x", expand=True)
        ttk.Button(pfad_rahmen, text="Auswählen", command=self._waehle_zielordner).pack(side="left", padx=(8, 0))
        ttk.Button(pfad_rahmen, text="Auto-Suche", command=self._auto_suche_systemag).pack(side="left", padx=(8, 0))

        aktions_rahmen = ttk.Frame(haupt)
        aktions_rahmen.pack(fill="x", pady=(10, 8))
        ttk.Button(aktions_rahmen, text="2) Prüfung laden", command=self.lade_diff).pack(side="left")
        ttk.Button(aktions_rahmen, text="3) Änderungen anwenden", command=self.wende_aenderungen_an).pack(side="left", padx=(8, 0))

        self._abbrechen_button = ttk.Button(aktions_rahmen, text="Abbrechen", command=self._beende_assistent)
        self._abbrechen_button.pack(side="right")
        self._schliessen_button = ttk.Button(
            aktions_rahmen,
            text="Schließen",
            command=self._beende_assistent,
            state="disabled",
        )
        self._schliessen_button.pack(side="right", padx=(0, 8))

        self._diff_text = tk.Text(haupt, height=18, wrap="word", state="disabled")
        self._diff_text.pack(fill="both", expand=True, pady=(0, 10))

        abschluss = ttk.LabelFrame(haupt, text="4) Abschluss", padding=10)
        abschluss.pack(fill="x")
        self._abschluss_var = tk.StringVar(value="Noch keine Ausführung vorhanden.")
        ttk.Label(abschluss, textvariable=self._abschluss_var, justify="left").pack(anchor="w")

        ttk.Label(haupt, textvariable=self._status_var).pack(anchor="w", pady=(8, 0))

    def _waehle_zielordner(self) -> None:
        """Öffnet den OS-Dialog zur Pfadwahl und aktualisiert den Zustand."""
        auswahl = filedialog.askdirectory(parent=self.window, title="Zielordner für die SystemAG-Struktur wählen")
        if auswahl:
            self._zielordner_var.set(auswahl)
            self._status_var.set("Zielordner gesetzt. Laden Sie jetzt die Bestandsprüfung.")

    def _auto_suche_systemag(self) -> None:
        """Sucht automatisch vorhandene ``SystemAG``-Ordner und wählt den besten Kandidaten."""
        kandidaten = finde_systemag_kandidaten()
        if not kandidaten:
            messagebox.showinfo(
                "Auto-Suche",
                "Es wurde kein vorhandener Ordner mit dem Namen 'SystemAG' gefunden.",
                parent=self.window,
            )
            self._status_var.set("Auto-Suche abgeschlossen: Kein vorhandener SystemAG-Ordner gefunden.")
            return

        self._kandidatenanalyse = pruefe_systemag_kandidaten(kandidaten)
        bevorzugt = next((k for k in self._kandidatenanalyse if k.ist_vollstaendig), self._kandidatenanalyse[0])
        self._zielordner_var.set(str(bevorzugt.pfad))

        text = (
            f"Auto-Suche: {len(kandidaten)} Kandidaten gefunden. "
            f"Ausgewählt wurde: {bevorzugt.pfad}"
        )
        self._status_var.set(text)

    def lade_diff(self) -> None:
        """Plant Freigabeänderungen und zeigt den Soll/Ist-Vergleich strukturiert an."""
        zielordner = self._zielordner_var.get().strip()
        if not zielordner:
            messagebox.showwarning("Ungültiger Pfad", "Bitte zuerst einen Zielordner eintragen.", parent=self.window)
            return

        kandidaten_pfade = [k.pfad for k in self._kandidatenanalyse]
        self._plan = plane_freigabeaenderungen(zielordner, kandidaten_pfade=kandidaten_pfade)
        fehlende_ordner = ermittle_fehlende_ordner(Path(zielordner))

        bericht = erstelle_verstaendlichen_bericht(zielordner, self._plan, fehlende_ordner)
        self._setze_diff_text(bericht)

        geaendert = [eintrag for eintrag in self._plan if eintrag.aktion != "noop"]
        self._status_var.set(
            f"Prüfung geladen: {len(self._plan)} Freigaben geprüft, {len(geaendert)} Änderungen erforderlich."
        )

    def wende_aenderungen_an(self) -> None:
        """Bestätigt und führt die geplanten Ordner-/Freigabeänderungen aus."""
        if self._aktion_laeuft:
            messagebox.showinfo(
                "Aktion läuft",
                "Die Verarbeitung läuft bereits. Bitte warten Sie, bis der Vorgang abgeschlossen ist.",
                parent=self.window,
            )
            return

        zielordner = self._zielordner_var.get().strip()
        if not zielordner:
            messagebox.showwarning("Pfad fehlt", "Bitte geben Sie zuerst einen Zielordner an.", parent=self.window)
            return

        if not self._plan:
            self.lade_diff()

        fehlende_ordner_vorher = ermittle_fehlende_ordner(Path(zielordner))
        if self._ist_struktur_vollstaendig_unbekannt(zielordner, fehlende_ordner_vorher):
            if not self._frage_struktur_anlegen(len(fehlende_ordner_vorher), zielordner):
                self._status_var.set("Abgebrochen: Struktur wurde nicht angelegt.")
                return

        geaendert = [eintrag for eintrag in self._plan if eintrag.aktion != "noop"]
        bestaetigungstext = "\n".join(e.diff_text for e in geaendert) if geaendert else "Keine Änderungen erforderlich."
        if geaendert and not messagebox.askyesno(
            "Änderungen bestätigen",
            f"Folgende Änderungen werden jetzt ausgeführt:\n\n{bestaetigungstext}",
            parent=self.window,
        ):
            self._status_var.set("Abgebrochen: Es wurden keine Änderungen durchgeführt.")
            return

        self._setze_aktionsstatus(laeuft=True)
        try:
            lauf_id = erstelle_lauf_id()
            setze_lauf_id(lauf_id)
            zeitstempel = datetime.now().isoformat(timespec="seconds")

            ergebnisse = pruefe_und_erstelle_struktur(zielordner, bestaetigung=lambda _diff: True)
            abschlussmeldungen = erstelle_abschlussmeldungen(fehlende_ordner_vorher, ergebnisse)
            self._abschluss_var.set("\n".join(abschlussmeldungen))

            protokoll = baue_ordnerlauf_protokoll(
                lauf_id=lauf_id,
                zeitstempel=zeitstempel,
                basis_pfad=zielordner,
                plan=self._plan,
                ergebnisse=ergebnisse,
                abschlussmeldungen=abschlussmeldungen,
            )
            protokoll_pfad = self._speichere_protokoll(protokoll)
            self._aktualisiere_modulzustand(zielordner, protokoll, protokoll_pfad)

            self._letzter_lauf_erfolgreich = True
            self._setze_schliessen_hervorgehoben()
            self._status_var.set(f"Fertig: Die Verarbeitung wurde erfolgreich abgeschlossen (Lauf-ID: {lauf_id}).")
            messagebox.showinfo(
                "Verarbeitung abgeschlossen",
                (
                    "Die Ordner- und Freigabestruktur wurde erfolgreich verarbeitet.\n\n"
                    f"Lauf-ID: {lauf_id}\n"
                    f"Protokoll: {protokoll_pfad}\n\n"
                    "Sie können den Assistenten jetzt über „Schließen“ beenden."
                ),
                parent=self.window,
            )
        finally:
            self._setze_aktionsstatus(laeuft=False)

    def _ist_struktur_vollstaendig_unbekannt(self, zielordner: str, fehlende_ordner: list[Path]) -> bool:
        """Erkennt den Fall, dass im Zielordner noch keine verwertbare Struktur vorliegt."""
        return not Path(zielordner).exists() or len(fehlende_ordner) == len(STANDARD_ORDNER)

    def _frage_struktur_anlegen(self, fehlende_anzahl: int, zielordner: str) -> bool:
        """Geführte Rückfrage inklusive transparenter Folgenbeschreibung."""
        return messagebox.askyesno(
            "Struktur jetzt anlegen?",
            (
                "Im ausgewählten Zielordner wurde noch keine vollständige SystemAG-Struktur gefunden.\n\n"
                f"Zielordner: {zielordner}\n"
                f"Fehlende Standardunterordner: {fehlende_anzahl}\n\n"
                "Folgen bei "
                "Ja:\n"
                "• Standardordner werden erstellt.\n"
                "• Freigaben werden auf Sollzustand gebracht.\n"
                "• Der Zielordner wird als bestätigter Pfad gespeichert.\n\n"
                "Folgen bei Nein:\n"
                "• Es werden keine Änderungen durchgeführt."
            ),
            parent=self.window,
        )

    def _setze_aktionsstatus(self, *, laeuft: bool) -> None:
        """Steuert den Laufstatus und verhindert Bedienfehler während der Verarbeitung."""
        self._aktion_laeuft = laeuft
        if laeuft:
            self._status_var.set("Verarbeitung läuft … Bitte warten.")
        self.window.update_idletasks()

    def _setze_schliessen_hervorgehoben(self) -> None:
        """Aktiviert den Abschlussbutton sichtbar nach erfolgreichem Lauf."""
        if self._schliessen_button is None:
            return
        self._schliessen_button.configure(state="normal", text="✅ Schließen")
        self._schliessen_button.focus_set()

    def _beende_assistent(self) -> None:
        """Beendet den Assistenten mit einer klaren, deutschsprachigen Rückfrage."""
        if self._aktion_laeuft:
            bestaetigt = messagebox.askyesno(
                "Verarbeitung läuft",
                "Der Vorgang läuft noch.\nMöchten Sie den Assistenten trotzdem schließen?",
                parent=self.window,
            )
            if not bestaetigt:
                return
        elif not self._letzter_lauf_erfolgreich:
            bestaetigt = messagebox.askyesno(
                "Assistent schließen",
                "Möchten Sie den Assistenten ohne abgeschlossene Verarbeitung schließen?",
                parent=self.window,
            )
            if not bestaetigt:
                return

        self.window.destroy()

    def _setze_diff_text(self, text: str) -> None:
        self._diff_text.configure(state="normal")
        self._diff_text.delete("1.0", tk.END)
        self._diff_text.insert(tk.END, text)
        self._diff_text.configure(state="disabled")

    def _speichere_protokoll(self, protokoll: dict[str, Any]) -> str:
        """Schreibt ein strukturiertes JSON-Protokoll pro Lauf."""
        dateiname = f"{protokoll['lauf_id']}_{protokoll['zeitstempel'].replace(':', '-')}.json"
        ziel = Path("logs") / "folder_gui_runs" / dateiname
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(json.dumps(protokoll, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(ziel)

    def _aktualisiere_modulzustand(self, zielordner: str, protokoll: dict[str, Any], protokoll_pfad: str) -> None:
        """Speichert Kernergebnisse inkl. bestätigtem Zielpfad für Folgeläufe."""
        self.modulzustand.setdefault("ausgabepfade", {})["basis_pfad"] = zielordner
        self.modulzustand.setdefault("ausgabepfade", {})["bestaetigter_zielpfad"] = zielordner
        self.modulzustand.setdefault("ausgabepfade", {})["letztes_protokoll"] = protokoll_pfad
        self.modulzustand["letzte_kerninfos"] = [
            f"Lauf-ID: {protokoll['lauf_id']}",
            f"Ausführung: {protokoll['zeitstempel']}",
            f"Zielordner: {zielordner}",
            f"Ergebnis: {protokoll['abschlussmeldungen'][0] if protokoll.get('abschlussmeldungen') else 'n/a'}",
        ]
        self.modulzustand["bericht_verweise"] = [protokoll_pfad]
        self.modulzustand["letztes_ergebnis"] = protokoll
        historie = self.modulzustand.setdefault("laufhistorie", [])
        historie.append(protokoll)
        self.modulzustand["laufhistorie"] = historie[-20:]

        self.state_store.speichere_modulzustand("folder_manager", self.modulzustand)


def _json_sicher(daten: Any) -> Any:
    """Konvertiert komplexe Strukturen (z. B. Sets) in JSON-kompatible Werte."""
    if isinstance(daten, dict):
        return {key: _json_sicher(value) for key, value in daten.items()}
    if isinstance(daten, list):
        return [_json_sicher(eintrag) for eintrag in daten]
    if isinstance(daten, set):
        return sorted(_json_sicher(eintrag) for eintrag in daten)
    return daten


def erstelle_verstaendlichen_bericht(
    zielordner: str,
    plan: list[FreigabeAenderung],
    fehlende_ordner: list[Path],
) -> str:
    """Strukturiert die Berichtsansicht in Problem/Auswirkung/Maßnahme/Begründung."""
    problemteile: list[str] = []
    if fehlende_ordner:
        problemteile.append(f"Es fehlen {len(fehlende_ordner)} Standardunterordner.")

    geaenderte = [p for p in plan if p.aktion != "noop"]
    if geaenderte:
        problemteile.append(f"{len(geaenderte)} Freigaben weichen vom Sollzustand ab.")

    problem = " ".join(problemteile) if problemteile else "Kein Problem festgestellt."
    auswirkung = (
        "Bei Abweichungen können Sage-Komponenten nicht konsistent auf Daten und Updates zugreifen."
        if geaenderte or fehlende_ordner
        else "Es sind keine betrieblichen Einschränkungen zu erwarten."
    )
    massnahme = (
        "Prüfung bestätigen und Struktur/Freigaben automatisch auf Sollzustand bringen."
        if geaenderte or fehlende_ordner
        else "Keine Maßnahme erforderlich."
    )
    begruendung = (
        "Die automatische Korrektur stellt eine standardisierte, wiederholbare Serverkonfiguration sicher."
        if geaenderte or fehlende_ordner
        else "Alle geprüften Kriterien entsprechen bereits dem definierten Zielzustand."
    )

    details = "\n".join(f"- {eintrag.diff_text.strip()}" for eintrag in plan) if plan else "- Keine Freigaben geprüft."
    return (
        f"Zielordner: {zielordner}\n\n"
        f"Problem:\n{problem}\n\n"
        f"Auswirkung:\n{auswirkung}\n\n"
        f"Empfohlene Maßnahme:\n{massnahme}\n\n"
        f"Begründung:\n{begruendung}\n\n"
        f"Technische Details (Soll/Ist):\n{details}"
    )


def erstelle_abschlussmeldungen(fehlende_ordner_vorher: list[Path], ergebnisse: list[FreigabeErgebnis]) -> list[str]:
    """Erzeugt explizite Abschlussindikatoren für den Assistenten."""
    ordner_vorhanden_text = (
        "Ordner vorhanden: ja (Struktur war bereits vollständig)."
        if not fehlende_ordner_vorher
        else f"Ordner vorhanden: ja (fehlende Ordner ergänzt: {len(fehlende_ordner_vorher)})."
    )
    freigaben_ergänzt = any(ergebnis.aktion in {"create", "update"} and ergebnis.erfolg for ergebnis in ergebnisse)
    freigaben_text = "Freigaben ergänzt: ja." if freigaben_ergänzt else "Freigaben ergänzt: nein."
    keine_aktion_noetig = bool(ergebnisse) and all(ergebnis.aktion == "noop" for ergebnis in ergebnisse)
    no_op_text = "Keine Aktion nötig: ja." if keine_aktion_noetig else "Keine Aktion nötig: nein."
    return [ordner_vorhanden_text, freigaben_text, no_op_text]


def baue_ordnerlauf_protokoll(
    *,
    lauf_id: str,
    zeitstempel: str,
    basis_pfad: str,
    plan: list[FreigabeAenderung],
    ergebnisse: list[FreigabeErgebnis],
    abschlussmeldungen: list[str],
) -> dict[str, Any]:
    """Baut ein strukturiertes Laufprotokoll für Dateispeicherung und GUI-State."""
    return {
        "lauf_id": lauf_id,
        "zeitstempel": zeitstempel,
        "basis_pfad": basis_pfad,
        "plan": _json_sicher([asdict(eintrag) for eintrag in plan]),
        "ergebnisse": _json_sicher([asdict(ergebnis) for ergebnis in ergebnisse]),
        "abschlussmeldungen": abschlussmeldungen,
    }


def start_gui(master: tk.Misc | None = None) -> FolderWizardGUI:
    """Startet den Ordner-/Freigabeassistenten als eigene GUI oder Child-Window."""
    wizard = FolderWizardGUI(master)
    if master is None:
        wizard.window.mainloop()
    return wizard


def main() -> None:
    """Direkter Einstieg mit Installationsschutz (analog zu anderen GUI-Modulen)."""

    def _zeige_fehler(text: str) -> None:
        print(f"❌ {text}")

    def _frage_installation(_frage: str) -> bool:
        antwort = input("Installation starten? [j/N]: ").strip().lower()
        return antwort in {"j", "ja", "y", "yes"}

    freigegeben = verarbeite_installations_guard(
        pruefe_installationszustand(),
        modulname="Ordnerverwaltung",
        fehlermeldung_fn=_zeige_fehler,
        installationsfrage_fn=_frage_installation,
    )
    if not freigegeben:
        return

    start_gui()


if __name__ == "__main__":
    main()
