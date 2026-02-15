"""Tkinter-basierte GUI für den SystemManager-SageHelper.

Die GUI dient als einfacher Launcher für Installation, Analyse,
Ordnerverwaltung und Dokumentation.
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id

logger = konfiguriere_logger(__name__, dateiname="gui_manager.log")


class SystemManagerGUI:
    """Kapselt Aufbau und Verhalten der Desktop-Oberfläche."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        master.title("SystemManager-SageHelper GUI")
        master.geometry("500x420")

        self.label = tk.Label(
            master,
            text="Willkommen beim SystemManager-SageHelper!",
            font=("Arial", 14),
        )
        self.label.pack(pady=10)

        self.lauf_id_var = tk.StringVar(value="-")
        tk.Label(master, text="Aktuelle Lauf-ID:", font=("Arial", 10, "bold")).pack()
        tk.Label(master, textvariable=self.lauf_id_var, font=("Consolas", 10)).pack(pady=(0, 8))

        self.install_button = tk.Button(master, text="Installieren", command=self.installieren, width=25)
        self.install_button.pack(pady=5)

        self.server_analysis_button = tk.Button(
            master,
            text="Serveranalyse starten",
            command=self.serveranalyse,
            width=25,
        )
        self.server_analysis_button.pack(pady=5)

        self.folder_manager_button = tk.Button(
            master,
            text="Ordner verwalten",
            command=self.ordner_verwalten,
            width=25,
        )
        self.folder_manager_button.pack(pady=5)

        self.doc_generator_button = tk.Button(
            master,
            text="Dokumentation generieren",
            command=self.dokumentation_generieren,
            width=25,
        )
        self.doc_generator_button.pack(pady=5)

        self.quit_button = tk.Button(master, text="Beenden", command=master.quit, width=25)
        self.quit_button.pack(pady=5)

        self.log_label = tk.Label(master, text="Log-Ausgabe:", font=("Arial", 12))
        self.log_label.pack(pady=5)

        self.log_output = tk.Text(master, height=10, width=60, state="disabled")
        self.log_output.pack()

    def _starte_neuen_lauf(self) -> str:
        """Erzeugt pro Aktion eine neue Lauf-ID für konsistente Korrelation."""
        lauf_id = erstelle_lauf_id()
        setze_lauf_id(lauf_id)
        self.lauf_id_var.set(lauf_id)
        logger.info("Neuer GUI-Lauf gestartet")
        return lauf_id

    def installieren(self) -> None:
        """Startet den Installationsassistenten im aktuellen Python-Interpreter."""
        lauf_id = self._starte_neuen_lauf()
        self.log(f"[{lauf_id}] Starte die Installation...")
        try:
            subprocess.check_call([sys.executable, "scripts/install_assistant.py"])
            messagebox.showinfo("Erfolg", f"Installation abgeschlossen!\nLauf-ID: {lauf_id}")
        except subprocess.CalledProcessError as exc:
            logger.exception("Installation fehlgeschlagen")
            messagebox.showerror("Fehler", f"Fehler bei der Installation: {exc}\nLauf-ID: {lauf_id}")
        self.log(f"[{lauf_id}] Installation abgeschlossen.")

    def serveranalyse(self) -> None:
        """Startet die Serveranalyse-GUI."""
        self.execute_command("Serveranalyse", [sys.executable, "src/server_analysis_gui.py"])

    def ordner_verwalten(self) -> None:
        """Startet die Ordnerverwaltung."""
        self.execute_command("Ordnerverwaltung", [sys.executable, "src/folder_manager.py"])

    def dokumentation_generieren(self) -> None:
        """Startet den Dokumentationsgenerator."""
        self.execute_command("Dokumentation", [sys.executable, "src/doc_generator.py"])

    def execute_command(self, action_name: str, command: list[str]) -> None:
        """Führt ein externes Kommando aus und zeigt Logs/Fehler in der GUI an."""
        lauf_id = self._starte_neuen_lauf()
        self.log(f"[{lauf_id}] Starte {action_name}...")
        logger.info("Starte Kommando %s: %s", action_name, command)
        try:
            result = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
            self.log(result)
            messagebox.showinfo("Erfolg", f"{action_name} abgeschlossen!\nLauf-ID: {lauf_id}")
        except subprocess.CalledProcessError as exc:
            logger.exception("Fehler bei GUI-Kommando %s", action_name)
            self.log(exc.output)
            messagebox.showerror("Fehler", f"Fehler bei der Ausführung von {action_name}: {exc}\nLauf-ID: {lauf_id}")

    def log(self, message: str) -> None:
        """Hängt eine Logzeile unten in der GUI an."""
        self.log_output.config(state="normal")
        self.log_output.insert(tk.END, message + "\n")
        self.log_output.config(state="disabled")
        self.log_output.see(tk.END)


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    gui = SystemManagerGUI(root)
    root.mainloop()
