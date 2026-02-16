"""Tkinter-basierte Startoberfläche mit Dashboard und Karten-Navigation."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from systemmanager_sagehelper.gui_shell import GuiShell
from systemmanager_sagehelper.gui_state import GUIStateStore
from systemmanager_sagehelper.installation_state import install_workflow_befehl, pruefe_installationszustand
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from systemmanager_sagehelper.ui_theme import LAYOUT

logger = konfiguriere_logger(__name__, dateiname="gui_manager.log")


class SystemManagerGUI:
    """Kapselt Aufbau und Verhalten der Launcher-Oberfläche."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.geometry("1080x820")

        self.state_store = GUIStateStore()
        self.modulzustand = self.state_store.lade_modulzustand("gui_manager")

        self.shell = GuiShell(
            master,
            titel="SystemManager-SageHelper",
            untertitel="Dashboard für Analyse, Ordnermanagement und Dokumentation",
            on_save=self.speichern,
            on_back=self.zurueck,
            on_exit=self.master.quit,
        )

        self._karten_status: dict[str, tk.StringVar] = {}
        self._baue_dashboard()

    def _baue_dashboard(self) -> None:
        """Erzeugt die Startseite mit klaren Modul-Cards inklusive Statusanzeige."""
        dashboard = ttk.LabelFrame(self.shell.content_frame, text="Dashboard", style="Section.TLabelframe")
        dashboard.pack(fill="x", pady=(0, LAYOUT.padding_block))

        ttk.Label(
            dashboard,
            text="Module",
            style="Headline.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=LAYOUT.padding_inline, pady=(10, 4))
        ttk.Label(
            dashboard,
            text="Wählen Sie ein Modul und starten Sie die passende Aktion.",
            style="Subheadline.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=LAYOUT.padding_inline, pady=(0, 10))

        cards = ttk.Frame(dashboard)
        cards.grid(row=2, column=0, sticky="ew", padx=LAYOUT.padding_inline, pady=(0, 12))
        cards.columnconfigure((0, 1), weight=1)

        self._baue_modul_card(
            cards,
            zeile=0,
            spalte=0,
            titel="Installation",
            beschreibung="Installiert oder aktualisiert alle Kernkomponenten.",
            command=self.installieren,
            status_key="installation",
            button_text="Installation starten",
        )
        self._baue_modul_card(
            cards,
            zeile=0,
            spalte=1,
            titel="Serveranalyse",
            beschreibung="Öffnet die Mehrserveranalyse mit Rollen- und Discovery-Funktionen.",
            command=self.serveranalyse,
            status_key="serveranalyse",
            button_text="Analyse starten",
        )
        self._baue_modul_card(
            cards,
            zeile=1,
            spalte=0,
            titel="Ordnerverwaltung",
            beschreibung="Verwaltet Zielordner und Berechtigungsstrukturen.",
            command=self.ordner_verwalten,
            status_key="ordnerverwaltung",
            button_text="Ordner verwalten",
        )
        self._baue_modul_card(
            cards,
            zeile=1,
            spalte=1,
            titel="Dokumentation",
            beschreibung="Erzeugt Markdown-Dokumentation auf Basis der letzten Ergebnisse.",
            command=self.dokumentation_generieren,
            status_key="dokumentation",
            button_text="Dokumentation erzeugen",
        )

        self._baue_uebersichtsseite()
        self._aktualisiere_dashboard_status()

    def _baue_modul_card(
        self,
        parent: ttk.Frame,
        *,
        zeile: int,
        spalte: int,
        titel: str,
        beschreibung: str,
        command,
        status_key: str,
        button_text: str,
    ) -> None:
        """Erzeugt eine modulare Card mit Statusindikator und Primäraktion."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=LAYOUT.padding_block)
        card.grid(row=zeile, column=spalte, sticky="nsew", padx=6, pady=6)

        ttk.Label(card, text=titel, style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(card, text=beschreibung, style="Card.TLabel", wraplength=LAYOUT.card_breite).pack(
            anchor="w", pady=(6, 10)
        )

        status_var = tk.StringVar(value="Status: unbekannt")
        self._karten_status[status_key] = status_var
        ttk.Label(card, textvariable=status_var, style="Card.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Button(card, text=button_text, style="Primary.TButton", width=LAYOUT.button_breite, command=command).pack(
            anchor="w"
        )

    def _baue_uebersichtsseite(self) -> None:
        """Stellt je Modul Kerninfos und Berichtverweise aus der Persistenz dar."""
        rahmen = ttk.LabelFrame(
            self.shell.content_frame,
            text="Übersicht: letzte Analyseinformationen",
            style="Section.TLabelframe",
        )
        rahmen.pack(fill="both", expand=True)

        spalten = ("modul", "infos", "berichte")
        self.uebersicht = ttk.Treeview(rahmen, columns=spalten, show="headings", height=14)
        self.uebersicht.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        self.uebersicht.heading("modul", text="Modul")
        self.uebersicht.heading("infos", text="Letzte Kerninfos")
        self.uebersicht.heading("berichte", text="Berichtverweise")

        self.uebersicht.column("modul", width=180)
        self.uebersicht.column("infos", width=430)
        self.uebersicht.column("berichte", width=330)

        scrollbar = ttk.Scrollbar(rahmen, orient="vertical", command=self.uebersicht.yview)
        scrollbar.pack(side="right", fill="y", pady=8, padx=8)
        self.uebersicht.configure(yscrollcommand=scrollbar.set)

        self._lade_uebersichtszeilen()

    def _lade_uebersichtszeilen(self) -> None:
        """Lädt Übersichtsdaten aus allen bekannten Modulen in die Tabelle."""
        for item_id in self.uebersicht.get_children(""):
            self.uebersicht.delete(item_id)

        zustand = self.state_store.lade_gesamtzustand().get("modules", {})
        for modulname, modulwerte in zustand.items():
            infos = "; ".join(modulwerte.get("letzte_kerninfos", [])) or "Keine Daten"
            berichte = "; ".join(modulwerte.get("bericht_verweise", [])) or "Keine Verweise"
            self.uebersicht.insert("", "end", values=(modulname, infos, berichte))

    def _aktualisiere_dashboard_status(self) -> None:
        """Berechnet den Status je Modul für die Dashboard-Cards."""
        module = self.state_store.lade_gesamtzustand().get("modules", {})
        status_texte = {
            "installation": "Nicht ausgeführt",
            "serveranalyse": "Keine Analyse gespeichert",
            "ordnerverwaltung": "Keine Ordnerprüfung gespeichert",
            "dokumentation": "Keine Dokumentation gespeichert",
        }

        if module.get("installer"):
            status_texte["installation"] = "Bereits konfiguriert"
        if module.get("server_analysis", {}).get("letzte_kerninfos"):
            status_texte["serveranalyse"] = "Ergebnisse vorhanden"
        if module.get("folder_manager", {}).get("letzte_kerninfos"):
            status_texte["ordnerverwaltung"] = "Ergebnisse vorhanden"
        if module.get("doc_generator", {}).get("letzte_kerninfos"):
            status_texte["dokumentation"] = "Ergebnisse vorhanden"

        for key, var in self._karten_status.items():
            var.set(f"Status: {status_texte.get(key, 'unbekannt')}")

    def _starte_neuen_lauf(self) -> str:
        """Erzeugt pro Aktion eine neue Lauf-ID für konsistente Korrelation."""
        lauf_id = erstelle_lauf_id()
        setze_lauf_id(lauf_id)
        self.shell.setze_lauf_id(lauf_id)
        logger.info("Neuer GUI-Lauf gestartet")
        return lauf_id

    def _execute_command(self, action_name: str, command: list[str]) -> None:
        """Führt ein externes Kommando aus und zeigt Status/Fehler in der Shell an."""
        if not self.shell.bestaetige_aktion(
            f"{action_name} bestätigen",
            f"Die Aktion '{action_name}' wird nun ausgeführt.",
        ):
            self.shell.setze_status(f"{action_name} abgebrochen")
            return

        lauf_id = self._starte_neuen_lauf()
        self.shell.setze_status(f"{action_name} läuft")
        self.shell.logge_meldung(f"[{lauf_id}] Starte {action_name}: {' '.join(command)}")
        try:
            result = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
            self.shell.logge_meldung(result.strip() or "(Keine Ausgabe)")
            self.shell.setze_status(f"{action_name} abgeschlossen")
            self.shell.zeige_erfolg(
                "Erfolg",
                f"{action_name} abgeschlossen.\nLauf-ID: {lauf_id}",
                "Prüfen Sie die Übersicht und speichern Sie bei Bedarf den Zustand.",
            )
        except subprocess.CalledProcessError as exc:
            logger.exception("Fehler bei GUI-Kommando %s", action_name)
            self.shell.logge_meldung(exc.output)
            self.shell.setze_status(f"{action_name} fehlgeschlagen")
            self.shell.zeige_fehler(
                "Fehler",
                f"Fehler bei der Ausführung von {action_name}: {exc}\nLauf-ID: {lauf_id}",
                "Öffnen Sie die Log-Ausgabe und beheben Sie die gemeldete Ursache.",
            )
        finally:
            self._lade_uebersichtszeilen()
            self._aktualisiere_dashboard_status()

    def installieren(self) -> None:
        """Startet den zentralen Installationsworkflow."""
        self._execute_command("Installation", install_workflow_befehl())

    def _installation_erforderlich_dialog(self, modulname: str) -> bool:
        """Blockiert Modulstarts ohne valide Installation und bietet direkt die Aktion an."""
        pruefung = pruefe_installationszustand()
        if pruefung.installiert:
            return True

        gruende = "\n- " + "\n- ".join(pruefung.gruende) if pruefung.gruende else ""
        self.shell.zeige_warnung(
            "Installation erforderlich",
            f"{modulname} ist noch nicht freigeschaltet.{gruende}",
            "Wählen Sie 'Ja', um jetzt den Installationsworkflow zu starten.",
        )
        if messagebox.askyesno(
            "Installation starten",
            f"{modulname} kann erst nach erfolgreicher Installation genutzt werden.\n\n"
            "Jetzt Installation starten?",
            parent=self.master,
        ):
            self.installieren()
        return False

    def serveranalyse(self) -> None:
        if not self._installation_erforderlich_dialog("Serveranalyse"):
            return
        self._execute_command("Serveranalyse", [sys.executable, "src/server_analysis_gui.py"])

    def ordner_verwalten(self) -> None:
        if not self._installation_erforderlich_dialog("Ordnerverwaltung"):
            return
        self._execute_command("Ordnerverwaltung", [sys.executable, "src/folder_manager.py"])

    def dokumentation_generieren(self) -> None:
        if not self._installation_erforderlich_dialog("Dokumentation"):
            return
        self._execute_command("Dokumentation", [sys.executable, "src/doc_generator.py"])

    def speichern(self) -> None:
        """Persistiert Launcher-relevante Einstellungen und aktualisiert die Übersicht."""
        self.modulzustand.setdefault("letzte_kerninfos", ["Launcher zuletzt geöffnet"])
        self.modulzustand.setdefault("bericht_verweise", [])
        self.state_store.speichere_modulzustand("gui_manager", self.modulzustand)
        self._lade_uebersichtszeilen()
        self._aktualisiere_dashboard_status()
        self.shell.setze_status("Launcher-Zustand gespeichert")
        self.shell.logge_meldung(f"Zustand gespeichert unter: {self.state_store.dateipfad}")

    def zurueck(self) -> None:
        """Navigationsaktion: im Launcher bedeutet Zurück eine Übersichts-Aktualisierung."""
        self._lade_uebersichtszeilen()
        self._aktualisiere_dashboard_status()
        self.shell.setze_status("Übersicht aktualisiert")


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    SystemManagerGUI(root)
    root.mainloop()
