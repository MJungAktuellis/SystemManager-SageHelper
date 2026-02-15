"""
gui_manager.py

Grafische Benutzeroberfläche (GUI) für den SystemManager-SageHelper.
Ermöglicht Benutzern die einfache Bedienung der Installation und der Module.
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import os

class SystemManagerGUI:
    def __init__(self, master):
        self.master = master
        master.title("SystemManager-SageHelper GUI")
        master.geometry("500x400")

        # Erstellen der Oberfläche
        self.label = tk.Label(master, text="Willkommen beim SystemManager-SageHelper!", font=("Arial", 14))
        self.label.pack(pady=10)

        # Buttons für Aktionen
        self.install_button = tk.Button(master, text="Installieren", command=self.installieren, width=25)
        self.install_button.pack(pady=5)

        self.server_analysis_button = tk.Button(master, text="Serveranalyse starten", command=self.serveranalyse, width=25)
        self.server_analysis_button.pack(pady=5)

        self.folder_manager_button = tk.Button(master, text="Ordner verwalten", command=self.ordner_verwalten, width=25)
        self.folder_manager_button.pack(pady=5)

        self.doc_generator_button = tk.Button(master, text="Dokumentation generieren", command=self.dokumentation_generieren, width=25)
        self.doc_generator_button.pack(pady=5)

        self.quit_button = tk.Button(master, text="Beenden", command=master.quit, width=25)
        self.quit_button.pack(pady=5)

        # Log-Ausgabe
        self.log_label = tk.Label(master, text="Log-Ausgabe:", font=("Arial", 12))
        self.log_label.pack(pady=5)

        self.log_output = tk.Text(master, height=10, width=60, state="disabled")
        self.log_output.pack()

    def installieren(self):
        self.log("Starte die Installation...")
        try:
            subprocess.check_call(["python", "scripts/install_assistant.py"])
            messagebox.showinfo("Erfolg", "Installation abgeschlossen!")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Fehler", f"Fehler bei der Installation: {e}")
        self.log("Installation abgeschlossen.")

    def serveranalyse(self):
        self.execute_command("Serveranalyse", ["python", "src/server_analysis.py"])

    def ordner_verwalten(self):
        self.execute_command("Ordnerverwaltung", ["python", "src/folder_manager.py"])

    def dokumentation_generieren(self):
        self.execute_command("Dokumentation", ["python", "src/doc_generator.py"])

    def execute_command(self, action_name, command):
        self.log(f"Starte {action_name}...")
        try:
            result = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
            self.log(result)
            messagebox.showinfo("Erfolg", f"{action_name} abgeschlossen!")
        except subprocess.CalledProcessError as e:
            self.log(e.output)
            messagebox.showerror("Fehler", f"Fehler bei der Ausführung von {action_name}: {e}")

    def log(self, message):
        self.log_output.config(state="normal")
        self.log_output.insert(tk.END, message + "\n")
        self.log_output.config(state="disabled")
        self.log_output.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    gui = SystemManagerGUI(root)
    root.mainloop()