"""Bestätigungsdialoge für geplante Änderungen (CLI und GUI)."""

from __future__ import annotations

from typing import Callable


def bestaetige_aenderungen_cli(diff_text: str, *, prompt: Callable[[str], str] = input) -> bool:
    """Zeigt das Änderungs-Diff in der CLI und fragt ``anwenden``/``abbrechen`` ab."""
    print("\nGeplante Share-Änderungen:\n")
    print(diff_text)
    antwort = prompt("Aktion wählen [anwenden/abbrechen]: ").strip().lower()
    return antwort == "anwenden"


def bestaetige_aenderungen_gui(diff_text: str) -> bool:
    """Öffnet einen einfachen Tk-Dialog mit Diff-Anzeige und zwei Aktionen."""
    import tkinter as tk
    from tkinter import ttk

    entscheidung = {"anwenden": False}
    fenster = tk.Toplevel()
    fenster.title("Share-Änderungen bestätigen")
    fenster.geometry("860x540")

    info = ttk.Label(
        fenster,
        text="Bitte prüfen Sie die geplanten Änderungen und wählen Sie 'anwenden' oder 'abbrechen'.",
        wraplength=820,
        justify="left",
    )
    info.pack(fill="x", padx=12, pady=(12, 8))

    text = tk.Text(fenster, wrap="word", height=24)
    text.pack(fill="both", expand=True, padx=12, pady=8)
    text.insert("1.0", diff_text)
    text.configure(state="disabled")

    button_frame = ttk.Frame(fenster)
    button_frame.pack(fill="x", padx=12, pady=(0, 12))

    def _anwenden() -> None:
        entscheidung["anwenden"] = True
        fenster.destroy()

    def _abbrechen() -> None:
        entscheidung["anwenden"] = False
        fenster.destroy()

    ttk.Button(button_frame, text="anwenden", command=_anwenden).pack(side="left")
    ttk.Button(button_frame, text="abbrechen", command=_abbrechen).pack(side="left", padx=(8, 0))

    fenster.transient(fenster.master)
    fenster.grab_set()
    fenster.wait_window()
    return entscheidung["anwenden"]
