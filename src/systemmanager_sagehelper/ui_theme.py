"""Zentrales Theming für alle Tkinter-/ttk-Oberflächen.

Das Modul bündelt Farbpalette, Typografie, Spacing und Zustandsfarben,
um eine durchgängige Bedienoberfläche sicherzustellen.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable


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
        self.style.configure("Card.Title.TLabel", background=PALETTE.oberflaeche, foreground=PALETTE.text, font=("Segoe UI", 12, "bold"))
        self.style.configure("Muted.TLabel", background=PALETTE.hintergrund, foreground=PALETTE.text_sekundaer)
        self.style.configure("Card.Muted.TLabel", background=PALETTE.oberflaeche, foreground=PALETTE.text_sekundaer)
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


def baue_card_baustein(
    parent: ttk.Widget,
    *,
    titel: tk.StringVar,
    beschreibung: tk.StringVar,
    status: tk.StringVar,
    primaer_text: str,
    primaer_aktion: Callable[[], None],
    sekundaer_text: str | None = None,
    sekundaer_aktion: Callable[[], None] | None = None,
    technische_details: tk.StringVar | None = None,
) -> dict[str, ttk.Widget]:
    """Erstellt einen wiederverwendbaren Card-Baustein mit Primäraktion.

    Die Card hält die Informationsdichte bewusst niedrig und blendet technische
    Details optional per Umschalter ein.
    """

    card = ttk.Frame(parent, style="Card.TFrame", padding=LAYOUT.padding_block)
    ttk.Label(card, textvariable=titel, style="Card.Title.TLabel").pack(anchor="w")
    ttk.Label(card, textvariable=beschreibung, style="Card.TLabel", wraplength=LAYOUT.card_breite).pack(anchor="w", pady=(6, 8))
    ttk.Label(card, textvariable=status, style="Card.Muted.TLabel", wraplength=LAYOUT.card_breite).pack(anchor="w", pady=(0, 10))

    primaer_button = ttk.Button(
        card,
        text=primaer_text,
        style="Primary.TButton",
        width=LAYOUT.button_breite,
        command=primaer_aktion,
    )
    primaer_button.pack(anchor="w")

    sekundaer_button: ttk.Button | None = None
    if sekundaer_text and sekundaer_aktion:
        sekundaer_button = ttk.Button(
            card,
            text=sekundaer_text,
            style="Secondary.TButton",
            width=LAYOUT.button_breite,
            command=sekundaer_aktion,
        )
        sekundaer_button.pack(anchor="w", pady=(6, 0))

    details_rahmen: ttk.Frame | None = None
    if technische_details is not None:
        details_sichtbar = tk.BooleanVar(value=False)
        details_rahmen = ttk.Frame(card)
        ttk.Label(details_rahmen, textvariable=technische_details, style="Card.Muted.TLabel", wraplength=LAYOUT.card_breite, justify="left").pack(anchor="w")

        def _toggle_details() -> None:
            if details_sichtbar.get():
                details_rahmen.pack_forget()
                details_sichtbar.set(False)
                details_button.configure(text="Technische Details anzeigen")
            else:
                details_rahmen.pack(anchor="w", fill="x", pady=(6, 0))
                details_sichtbar.set(True)
                details_button.configure(text="Technische Details ausblenden")

        details_button = ttk.Button(card, text="Technische Details anzeigen", style="Secondary.TButton", command=_toggle_details)
        details_button.pack(anchor="w", pady=(6, 0))

    return {
        "card": card,
        "primaer_button": primaer_button,
        "sekundaer_button": sekundaer_button,
        "details_rahmen": details_rahmen,
    }


__all__ = [
    "LAYOUT",
    "PALETTE",
    "TYPO",
    "STATE_COLORS",
    "ThemeManager",
    "baue_card_baustein",
]
