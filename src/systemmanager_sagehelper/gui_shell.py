"""Gemeinsames GUI-Shell-Konzept für Tkinter-Ansichten.

Die Shell stellt wiederverwendbare Bereiche bereit:
- einheitliche Kopfzeile
- Aktionsleiste (Speichern, Zurück, Beenden)
- Status-/Meldungsbereich
- Inhaltsbereich für modulspezifische Widgets
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class GuiShell:
    """Kapselt wiederkehrende GUI-Bereiche für konsistente Moduloberflächen."""

    def __init__(
        self,
        master: tk.Tk,
        *,
        titel: str,
        untertitel: str,
        on_save: Callable[[], None],
        on_back: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.master = master
        self.master.title(titel)

        self.status_var = tk.StringVar(value="Bereit")
        self.lauf_id_var = tk.StringVar(value="-")

        container = ttk.Frame(master, padding=12)
        container.pack(fill="both", expand=True)

        self._baue_kopfzeile(container, titel=titel, untertitel=untertitel)
        self._baue_aktionsleiste(container, on_save=on_save, on_back=on_back, on_exit=on_exit)

        self.content_frame = ttk.Frame(container)
        self.content_frame.pack(fill="both", expand=True, pady=(8, 8))

        self._baue_statusbereich(container)

    def _baue_kopfzeile(self, parent: ttk.Frame, *, titel: str, untertitel: str) -> None:
        kopf = ttk.Frame(parent)
        kopf.pack(fill="x")

        ttk.Label(kopf, text=titel, font=("Arial", 17, "bold")).pack(anchor="w")
        ttk.Label(kopf, text=untertitel).pack(anchor="w", pady=(2, 2))

        lauf_id_zeile = ttk.Frame(kopf)
        lauf_id_zeile.pack(anchor="w", pady=(2, 0))
        ttk.Label(lauf_id_zeile, text="Lauf-ID:", font=("Arial", 10, "bold")).pack(side="left")
        ttk.Label(lauf_id_zeile, textvariable=self.lauf_id_var, font=("Consolas", 10)).pack(side="left", padx=(6, 0))

    def _baue_aktionsleiste(
        self,
        parent: ttk.Frame,
        *,
        on_save: Callable[[], None],
        on_back: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        leiste = ttk.Frame(parent)
        leiste.pack(fill="x", pady=(10, 4))

        ttk.Button(leiste, text="Speichern", command=on_save).pack(side="left", padx=(0, 8))
        ttk.Button(leiste, text="Zurück", command=on_back).pack(side="left")
        ttk.Button(leiste, text="Beenden", command=on_exit).pack(side="right")

    def _baue_statusbereich(self, parent: ttk.Frame) -> None:
        rahmen = ttk.LabelFrame(parent, text="Status / Meldungen")
        rahmen.pack(fill="both", expand=False)

        ttk.Label(rahmen, textvariable=self.status_var).pack(anchor="w", padx=8, pady=(8, 4))

        self.meldungen = tk.Text(rahmen, height=6, width=120, state="disabled")
        self.meldungen.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def setze_lauf_id(self, lauf_id: str) -> None:
        """Aktualisiert die Lauf-ID in der Shell-Kopfzeile."""
        self.lauf_id_var.set(lauf_id)

    def setze_status(self, nachricht: str) -> None:
        """Setzt den aktuellen Status im Statusbereich."""
        self.status_var.set(nachricht)

    def logge_meldung(self, nachricht: str) -> None:
        """Fügt eine Zeile in die Meldungsbox ein und scrollt ans Ende."""
        self.meldungen.config(state="normal")
        self.meldungen.insert(tk.END, nachricht + "\n")
        self.meldungen.config(state="disabled")
        self.meldungen.see(tk.END)
