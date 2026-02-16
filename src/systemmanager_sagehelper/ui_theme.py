"""Zentrales Theming für alle Tkinter-/ttk-Oberflächen.

Das Modul bündelt Farbpalette, Typografie, Spacing und Zustandsfarben,
um eine durchgängige Bedienoberfläche sicherzustellen.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class Farbpalette:
    """Definiert alle Kernfarben für die Benutzeroberfläche."""

    hintergrund: str = "#F4F7FB"
    oberflaeche: str = "#FFFFFF"
    primar: str = "#1F6FEB"
    primar_aktiv: str = "#1559BF"
    text: str = "#1F2A37"
    text_sekundaer: str = "#4B5563"
    rahmen: str = "#D0D7E2"
    info: str = "#0EA5E9"
    warnung: str = "#D97706"
    fehler: str = "#DC2626"
    erfolg: str = "#16A34A"


@dataclass(frozen=True)
class Typografie:
    """Zentrale Schriftdefinitionen für konsistente Lesbarkeit."""

    standard: tuple[str, int] = ("Segoe UI", 10)
    label_fett: tuple[str, int, str] = ("Segoe UI", 10, "bold")
    titel: tuple[str, int, str] = ("Segoe UI", 18, "bold")
    untertitel: tuple[str, int] = ("Segoe UI", 11)
    code: tuple[str, int] = ("Consolas", 10)


@dataclass(frozen=True)
class Layout:
    """Standardisierte Abstände und Größen für Komponenten."""

    padding_gesamt: int = 16
    padding_block: int = 12
    padding_inline: int = 8
    button_breite: int = 22
    card_breite: int = 290
    card_hoehe: int = 150


PALETTE = Farbpalette()
TYPO = Typografie()
LAYOUT = Layout()

STATE_COLORS: dict[str, str] = {
    "info": PALETTE.info,
    "warnung": PALETTE.warnung,
    "fehler": PALETTE.fehler,
    "erfolg": PALETTE.erfolg,
}


class ThemeManager:
    """Konfiguriert ttk-Styles einmalig pro Root-Fenster."""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.style = ttk.Style(root)

    def anwenden(self) -> None:
        """Aktiviert das einheitliche Theme und registriert alle Styles."""
        self.style.theme_use("clam")

        self.root.configure(background=PALETTE.hintergrund)

        self.style.configure(".", background=PALETTE.hintergrund, foreground=PALETTE.text, font=TYPO.standard)
        self.style.configure("TFrame", background=PALETTE.hintergrund)
        self.style.configure(
            "Card.TFrame",
            background=PALETTE.oberflaeche,
            borderwidth=1,
            relief="solid",
            bordercolor=PALETTE.rahmen,
        )
        self.style.configure("TLabel", background=PALETTE.hintergrund, foreground=PALETTE.text)
        self.style.configure("Card.TLabel", background=PALETTE.oberflaeche, foreground=PALETTE.text)
        self.style.configure("Headline.TLabel", font=TYPO.titel)
        self.style.configure("Subheadline.TLabel", font=TYPO.untertitel, foreground=PALETTE.text_sekundaer)
        self.style.configure("Section.TLabelframe", background=PALETTE.hintergrund, bordercolor=PALETTE.rahmen)
        self.style.configure("Section.TLabelframe.Label", font=TYPO.label_fett)

        self.style.configure(
            "Primary.TButton",
            background=PALETTE.primar,
            foreground="#FFFFFF",
            borderwidth=0,
            focusthickness=3,
            focuscolor=PALETTE.primar_aktiv,
            padding=(12, 8),
        )
        self.style.map(
            "Primary.TButton",
            background=[("active", PALETTE.primar_aktiv), ("disabled", "#A7B4C7")],
            foreground=[("disabled", "#EAF0F8")],
        )
        self.style.configure("Secondary.TButton", padding=(10, 7))

        self.style.configure("TEntry", fieldbackground="#FFFFFF", bordercolor=PALETTE.rahmen, padding=5)
        self.style.configure("TCheckbutton", background=PALETTE.hintergrund)
        self.style.configure("Treeview", rowheight=26, fieldbackground="#FFFFFF", bordercolor=PALETTE.rahmen)
        self.style.configure("Treeview.Heading", font=TYPO.label_fett)

    def zustandsfarbe(self, status_typ: str) -> str:
        """Liefert die Farbe für eine definierte Statusklasse zurück."""
        return STATE_COLORS.get(status_typ, PALETTE.info)


__all__ = [
    "LAYOUT",
    "PALETTE",
    "TYPO",
    "STATE_COLORS",
    "ThemeManager",
]
