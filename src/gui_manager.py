"""Tkinter-basierte Startoberfläche mit gemeinsamem GUI-Shell-Konzept."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from systemmanager_sagehelper.gui_shell import GuiShell
from systemmanager_sagehelper.gui_state import GUIStateStore
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id

logger = konfiguriere_logger(__name__, dateiname="gui_manager.log")


class SystemManagerGUI:
    """Kapselt Aufbau und Verhalten der Launcher-Oberfläche."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.geometry("980x760")

        self.state_store = GUIStateStore()
        self.modulzustand = self.state_store.lade_modulzustand("gui_manager")

        self.shell = GuiShell(
            master,
            titel="SystemManager-SageHelper",
            untertitel="Zentrale Steuerung für Analyse, Ordnermanagement und Dokumentation",
            on_save=self.speichern,
            on_back=self.zurueck,
            on_exit=self.master.quit,
        )

        self._baue_modulaktionen()
        self._baue_uebersichtsseite()

    def _baue_modulaktionen(self) -> None:
        """Erzeugt die primären Launcher-Aktionen als schnelle Einstiegspunkte."""
        rahmen = ttk.LabelFrame(self.shell.content_frame, text="Module starten")
        rahmen.pack(fill="x", pady=(0, 10))

        ttk.Button(rahmen, text="Installieren", command=self.installieren).pack(side="left", padx=8, pady=8)
        ttk.Button(rahmen, text="Serveranalyse starten", command=self.serveranalyse).pack(side="left", padx=8)
        ttk.Button(rahmen, text="Ordner verwalten", command=self.ordner_verwalten).pack(side="left", padx=8)
        ttk.Button(rahmen, text="Dokumentation generieren", command=self.dokumentation_generieren).pack(
            side="left", padx=8
        )

    def _baue_uebersichtsseite(self) -> None:
        """Stellt je Modul Kerninfos und Berichtverweise aus der Persistenz dar."""
        rahmen = ttk.LabelFrame(self.shell.content_frame, text="Übersicht: letzte Analyseinformationen")
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

    def _starte_neuen_lauf(self) -> str:
        """Erzeugt pro Aktion eine neue Lauf-ID für konsistente Korrelation."""
        lauf_id = erstelle_lauf_id()
        setze_lauf_id(lauf_id)
        self.shell.setze_lauf_id(lauf_id)
        logger.info("Neuer GUI-Lauf gestartet")
        return lauf_id

    def _execute_command(self, action_name: str, command: list[str]) -> None:
        """Führt ein externes Kommando aus und zeigt Status/Fehler in der Shell an."""
        lauf_id = self._starte_neuen_lauf()
        self.shell.setze_status(f"{action_name} läuft")
        self.shell.logge_meldung(f"[{lauf_id}] Starte {action_name}: {' '.join(command)}")
        try:
            result = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
            self.shell.logge_meldung(result.strip() or "(Keine Ausgabe)")
            self.shell.setze_status(f"{action_name} abgeschlossen")
            messagebox.showinfo("Erfolg", f"{action_name} abgeschlossen.\nLauf-ID: {lauf_id}")
        except subprocess.CalledProcessError as exc:
            logger.exception("Fehler bei GUI-Kommando %s", action_name)
            self.shell.logge_meldung(exc.output)
            self.shell.setze_status(f"{action_name} fehlgeschlagen")
            messagebox.showerror("Fehler", f"Fehler bei der Ausführung von {action_name}: {exc}\nLauf-ID: {lauf_id}")

    def installieren(self) -> None:
        self._execute_command("Installation", [sys.executable, "scripts/install_assistant.py"])

    def serveranalyse(self) -> None:
        self._execute_command("Serveranalyse", [sys.executable, "src/server_analysis_gui.py"])

    def ordner_verwalten(self) -> None:
        self._execute_command("Ordnerverwaltung", [sys.executable, "src/folder_manager.py"])

    def dokumentation_generieren(self) -> None:
        self._execute_command("Dokumentation", [sys.executable, "src/doc_generator.py"])

    def speichern(self) -> None:
        """Persistiert Launcher-relevante Einstellungen und aktualisiert die Übersicht."""
        self.modulzustand.setdefault("letzte_kerninfos", ["Launcher zuletzt geöffnet"])
        self.modulzustand.setdefault("bericht_verweise", [])
        self.state_store.speichere_modulzustand("gui_manager", self.modulzustand)
        self._lade_uebersichtszeilen()
        self.shell.setze_status("Launcher-Zustand gespeichert")
        self.shell.logge_meldung(f"Zustand gespeichert unter: {self.state_store.dateipfad}")

    def zurueck(self) -> None:
        """Navigationsaktion: im Launcher bedeutet Zurück eine Übersichts-Aktualisierung."""
        self._lade_uebersichtszeilen()
        self.shell.setze_status("Übersicht aktualisiert")


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    SystemManagerGUI(root)
    root.mainloop()
