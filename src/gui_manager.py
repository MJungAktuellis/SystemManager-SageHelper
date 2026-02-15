"""Tkinter-basierte GUI für den SystemManager-SageHelper.

Die GUI dient als einfacher Launcher für Installation, Analyse,
Ordnerverwaltung und Dokumentation.
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import messagebox


class SystemManagerGUI:
    """Kapselt Aufbau und Verhalten der Desktop-Oberfläche."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        master.title("SystemManager-SageHelper GUI")
        master.geometry("500x400")

        self.label = tk.Label(
            master,
            text="Willkommen beim SystemManager-SageHelper!",
            font=("Arial", 14),
        )
        self.label.pack(pady=10)

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

    def installieren(self) -> None:
        """Startet den Installationsassistenten im aktuellen Python-Interpreter."""
        self.log("Starte die Installation...")
        try:
            subprocess.check_call([sys.executable, "scripts/install_assistant.py"])
            messagebox.showinfo("Erfolg", "Installation abgeschlossen!")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror("Fehler", f"Fehler bei der Installation: {exc}")
        self.log("Installation abgeschlossen.")

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
        self.log(f"Starte {action_name}...")
        try:
            result = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
            self.log(result)
            messagebox.showinfo("Erfolg", f"{action_name} abgeschlossen!")
        except subprocess.CalledProcessError as exc:
            self.log(exc.output)
            messagebox.showerror("Fehler", f"Fehler bei der Ausführung von {action_name}: {exc}")

    def log(self, message: str) -> None:
        """Hängt eine Logzeile unten in der GUI an."""
        self.log_output.config(state="normal")
        self.log_output.insert(tk.END, message + "\n")
        self.log_output.config(state="disabled")
        self.log_output.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    gui = SystemManagerGUI(root)
    root.mainloop()
