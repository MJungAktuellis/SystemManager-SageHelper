"""Gemeinsames GUI-Shell-Konzept für Tkinter-Ansichten.

Die Shell stellt wiederverwendbare Bereiche bereit:
- einheitliche Kopfzeile
- Aktionsleiste (Speichern, Zurück, Beenden)
- Status-/Meldungsbereich
- Inhaltsbereich für modulspezifische Widgets
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from systemmanager_sagehelper.texte import (
    BUTTON_BEENDEN,
    BUTTON_SPEICHERN,
    BUTTON_ZURUECK,
    STATUS_HINWEIS,
)
from systemmanager_sagehelper.ui_theme import LAYOUT, PALETTE, TYPO, ThemeManager


class GuiShell:
    """Kapselt wiederkehrende GUI-Bereiche für konsistente Moduloberflächen."""

    def __init__(
        self,
        master: tk.Tk,
        *,
        titel: str,
        untertitel: str,
        on_save: Callable[[], None] | None = None,
        on_back: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
        show_actions: bool = True,
        show_save_action: bool = True,
        show_back_action: bool = True,
        show_exit_action: bool = True,
    ) -> None:
        self.master = master
        self.master.title(titel)
        self.theme = ThemeManager(master)
        self.theme.anwenden()

        self.status_var = tk.StringVar(value=f"{STATUS_HINWEIS} Bereit")
        self.lauf_id_var = tk.StringVar(value="-")

        container = ttk.Frame(master, padding=LAYOUT.padding_gesamt)
        container.pack(fill="both", expand=True)

        self._baue_kopfzeile(container, titel=titel, untertitel=untertitel)
        # Die Shell kann optional ohne globale Aktionsleiste verwendet werden,
        # z. B. in Wizarden mit eigener, schrittspezifischer Navigation.
        if show_actions:
            self._baue_aktionsleiste(
                container,
                on_save=on_save,
                on_back=on_back,
                on_exit=on_exit,
                show_save_action=show_save_action,
                show_back_action=show_back_action,
                show_exit_action=show_exit_action,
            )

        self.content_frame = ttk.Frame(container)
        self.content_frame.pack(fill="both", expand=True, pady=(LAYOUT.padding_inline, LAYOUT.padding_inline))

        self._baue_statusbereich(container)

    def _baue_kopfzeile(self, parent: ttk.Frame, *, titel: str, untertitel: str) -> None:
        kopf = ttk.Frame(parent)
        kopf.pack(fill="x")

        ttk.Label(kopf, text=titel, style="Headline.TLabel").pack(anchor="w")
        ttk.Label(kopf, text=untertitel, style="Subheadline.TLabel").pack(anchor="w", pady=(2, 2))

        lauf_id_zeile = ttk.Frame(kopf)
        lauf_id_zeile.pack(anchor="w", pady=(2, 0))
        ttk.Label(lauf_id_zeile, text="Lauf-ID:", font=TYPO.label_fett).pack(side="left")
        ttk.Label(lauf_id_zeile, textvariable=self.lauf_id_var, font=TYPO.code).pack(side="left", padx=(6, 0))

    def _baue_aktionsleiste(
        self,
        parent: ttk.Frame,
        *,
        on_save: Callable[[], None] | None,
        on_back: Callable[[], None] | None,
        on_exit: Callable[[], None] | None,
        show_save_action: bool,
        show_back_action: bool,
        show_exit_action: bool,
    ) -> None:
        leiste = ttk.Frame(parent)
        leiste.pack(fill="x", pady=(10, 4))

        if show_save_action and on_save is not None:
            ttk.Button(leiste, text=BUTTON_SPEICHERN, style="Secondary.TButton", command=on_save).pack(
                side="left", padx=(0, 8)
            )
        if show_back_action and on_back is not None:
            ttk.Button(leiste, text=BUTTON_ZURUECK, style="Secondary.TButton", command=on_back).pack(side="left")
        if show_exit_action and on_exit is not None:
            ttk.Button(leiste, text=BUTTON_BEENDEN, style="Secondary.TButton", command=on_exit).pack(side="right")

    def _baue_statusbereich(self, parent: ttk.Frame) -> None:
        rahmen = ttk.LabelFrame(parent, text="Status / Meldungen", style="Section.TLabelframe")
        rahmen.pack(fill="both", expand=False)

        ttk.Label(rahmen, textvariable=self.status_var).pack(anchor="w", padx=8, pady=(8, 4))

        self.meldungen = tk.Text(
            rahmen,
            height=6,
            width=120,
            state="disabled",
            background="#FFFFFF",
            foreground=PALETTE.text,
            font=TYPO.standard,
            borderwidth=1,
            relief="solid",
        )
        self.meldungen.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def bestaetige_aktion(self, titel: str, nachricht: str) -> bool:
        """Fragt eine bestätigte Primäraktion konsistent über die Shell ab."""
        return messagebox.askokcancel(titel, f"{nachricht}\n\nBitte prüfen und anschließend bestätigen.", parent=self.master)

    def zeige_erfolg(self, titel: str, nachricht: str, empfehlung: str) -> None:
        """Zeigt einen standardisierten Erfolgsdialog mit nächstem Schritt."""
        messagebox.showinfo(titel, f"{nachricht}\n\nNächster Schritt: {empfehlung}", parent=self.master)

    def zeige_info(self, titel: str, nachricht: str, empfehlung: str) -> None:
        """Zeigt einen standardisierten Informationsdialog mit Handlungsempfehlung."""
        messagebox.showinfo(titel, f"{nachricht}\n\nEmpfehlung: {empfehlung}", parent=self.master)

    def zeige_warnung(self, titel: str, nachricht: str, empfehlung: str) -> None:
        """Zeigt eine standardisierte Warnung mit Handlungsempfehlung."""
        messagebox.showwarning(titel, f"{nachricht}\n\nEmpfehlung: {empfehlung}", parent=self.master)

    def zeige_fehler(self, titel: str, nachricht: str, empfehlung: str) -> None:
        """Zeigt einen standardisierten Fehlerdialog mit nächster Aktion."""
        messagebox.showerror(titel, f"{nachricht}\n\nEmpfehlung: {empfehlung}", parent=self.master)

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
