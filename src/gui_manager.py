"""Tkinter-basierte Startoberfläche mit Dashboard und geführtem Onboarding."""

from __future__ import annotations

from datetime import datetime
import ipaddress
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from systemmanager_sagehelper.analyzer import DiscoveryKonfiguration, analysiere_mehrere_server, entdecke_server_ergebnisse
from systemmanager_sagehelper.gui_shell import GuiShell
from systemmanager_sagehelper.gui_state import GUIStateStore
from systemmanager_sagehelper.installation_state import pruefe_installationszustand
from systemmanager_sagehelper.folder_gui import FolderWizardGUI
from systemmanager_sagehelper.installer_gui import InstallerWizardGUI
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from systemmanager_sagehelper.discovery_rollen import ableite_rollen_aus_discoveryindikatoren, formatiere_erreichbarkeitsstatus
from systemmanager_sagehelper.models import AnalyseErgebnis
from systemmanager_sagehelper.targeting import normalisiere_servernamen
from systemmanager_sagehelper.update_strategy import ermittle_update_kontext
from systemmanager_sagehelper.texte import (
    STATUS_PREFIX,
)
from systemmanager_sagehelper.ui_theme import LAYOUT, baue_card_baustein
from server_analysis_gui import (
    ServerAnalysePersistenzDaten,
    ServerTabellenZeile,
    _baue_server_summary,
    _baue_serverziele,
    _integriere_manuelle_anmerkungen,
    persistiere_serveranalyse_zustand,
)

logger = konfiguriere_logger(__name__, dateiname="gui_manager.log")


def _formatiere_server_summary_fuer_dashboard(server_summary: list[dict[str, object]], *, limit: int = 5) -> str:
    """Erzeugt gut lesbare Statuszeilen aus dem persistierten Server-Snapshot.

    Die Darstellung ist bewusst kompakt gehalten, damit sie in der
    Dashboard-Übersicht mit weiteren Modulen zusammen lesbar bleibt.
    """
    if not server_summary:
        return "Keine Analyse vorhanden – bitte zuerst Serveranalyse starten."

    zeilen: list[str] = []
    for server in server_summary[:limit]:
        name = str(server.get("name") or "unbekannt")
        rollen = ", ".join(server.get("rollen", [])) or "keine Rolle"
        status = "erreichbar" if bool(server.get("erreichbar")) else "nicht erreichbar"
        quelle = str(server.get("rollenquelle") or "unbekannt")
        zeilen.append(f"{name}: {rollen} ({status}, Quelle: {quelle})")

    if len(server_summary) > limit:
        zeilen.append(f"… +{len(server_summary) - limit} weitere Server")

    return " | ".join(zeilen)

_ONBOARDING_VERSION = "1.0.0"
_STANDARD_ONBOARDING_ABBRUCH_AKTION = "app_schliessen"


class OnboardingController:
    """Kapselt den Erststart-Workflow strikt getrennt vom regulären Dashboard-Betrieb.

    Die Klasse orchestriert bewusst nur den Onboarding-Pfad und nutzt dafür
    etablierte Bausteine aus der Serveranalyse-GUI (Tabellenmodell + Persistenz),
    damit keine Logik doppelt implementiert werden muss.
    """

    def __init__(self, gui: "SystemManagerGUI") -> None:
        self.gui = gui
        self.state_store = gui.state_store
        self.server_zeilen: list[ServerTabellenZeile] = []
        self.analyse_ergebnisse: list[AnalyseErgebnis] = []

        # Interner UI-Status für den Wizard.
        self._window: tk.Toplevel | None = None
        self._status_var: tk.StringVar | None = None
        self._analyse_pfad_var: tk.StringVar | None = None
        self._scanbereich_var: tk.StringVar | None = None
        self._erweitert_aktiv_var: tk.BooleanVar | None = None

        # Schrittsteuerung und Statusdarstellung für den geführten Wizard.
        self._schritt_buttons: dict[str, ttk.Button] = {}
        self._schritt_status_var: dict[str, tk.StringVar] = {}
        self._schritt_aktion_var: dict[str, tk.StringVar] = {}
        self._schritt_reihenfolge = ["discovery", "rollen", "analyse", "speichern"]
        self._schritt_position = {schritt: index for index, schritt in enumerate(self._schritt_reihenfolge)}
        self._aktueller_schritt = "discovery"
        self._freigeschalteter_schritt_index = 0
        self._discovery_bereiche: list[tuple[str, int, int]] = []
        self._gespeicherter_scanbereich = ""

    def starte_wizard(self) -> None:
        """Öffnet den geführten Onboarding-Wizard als modalen Dialog."""
        if self._window and self._window.winfo_exists():
            self._window.lift()
            return

        self._window = tk.Toplevel(self.gui.master)
        self._window.title("Erststart-Assistent")
        self._window.geometry("980x720")
        self._window.minsize(900, 620)
        self._window.transient(self.gui.master)
        self._window.grab_set()
        self._window.protocol("WM_DELETE_WINDOW", self._abbrechen)

        self._status_var = tk.StringVar(value="Bereit: Schritt 1 starten (Netzwerkerkennung).")
        self._analyse_pfad_var = tk.StringVar(value="docs/serverbericht.md")
        self._scanbereich_var = tk.StringVar(value="Scanbereich wird automatisch aus der lokalen Netzwerkkonfiguration ermittelt …")
        self._erweitert_aktiv_var = tk.BooleanVar(value=False)

        # Kleines Display-Fallback: Bei niedriger Bildschirmhöhe wird der Wizard-Inhalt
        # in einen Canvas mit vertikalem Scrollbar gerendert, damit keine Felder abgeschnitten werden.
        nutzt_scrollcontainer = self._window.winfo_screenheight() <= 800
        rahmen: ttk.Frame
        if nutzt_scrollcontainer:
            scroll_host = ttk.Frame(self._window)
            scroll_host.pack(fill="both", expand=True)

            inhalt_canvas = tk.Canvas(scroll_host, highlightthickness=0)
            vertikale_scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=inhalt_canvas.yview)
            inhalt_canvas.configure(yscrollcommand=vertikale_scrollbar.set)

            inhalt_canvas.pack(side="left", fill="both", expand=True)
            vertikale_scrollbar.pack(side="right", fill="y")

            rahmen = ttk.Frame(inhalt_canvas, padding=16)
            canvas_window = inhalt_canvas.create_window((0, 0), window=rahmen, anchor="nw")

            def _aktualisiere_scrollregion(_event: tk.Event) -> None:
                inhalt_canvas.configure(scrollregion=inhalt_canvas.bbox("all"))

            def _aktualisiere_rahmenbreite(event: tk.Event) -> None:
                inhalt_canvas.itemconfigure(canvas_window, width=event.width)

            rahmen.bind("<Configure>", _aktualisiere_scrollregion)
            inhalt_canvas.bind("<Configure>", _aktualisiere_rahmenbreite)
        else:
            rahmen = ttk.Frame(self._window, padding=16)
            rahmen.pack(fill="both", expand=True)

        ttk.Label(
            rahmen,
            text="Geführtes Onboarding",
            style="Headline.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            rahmen,
            text=(
                "Folgen Sie den 4 Schritten: Netzwerkerkennung → Rollen prüfen → Analyse ausführen → Speichern/Bestätigen.\n"
                "Der Standardpfad nutzt automatisch den lokalen Netzbereich und hält den Ablauf bewusst geführt."
            ),
            justify="left",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 14))

        ttk.Label(rahmen, text="Automatisch abgeleiteter Netzscanbereich:").pack(anchor="w")
        ttk.Entry(rahmen, textvariable=self._scanbereich_var, width=58, state="readonly").pack(anchor="w", pady=(2, 8))

        erweitert_rahmen = ttk.LabelFrame(rahmen, text="Erweiterter Pfad", style="Section.TLabelframe")
        erweitert_rahmen.pack(fill="x", pady=(0, 10))
        self._erweitert_toggle = ttk.Checkbutton(
            erweitert_rahmen,
            text="Erweiterten Netzscan nach zusätzlicher Bestätigung aktivieren",
            variable=self._erweitert_aktiv_var,
            command=self._umschalten_erweiterten_pfad,
        )
        self._erweitert_toggle.pack(anchor="w", padx=8, pady=(6, 4))

        self._erweitert_hinweis = ttk.Label(
            erweitert_rahmen,
            text="Standard: kein freier Bereichseintrag. Optional kann ein CIDR/Bereich hinterlegt werden.",
            justify="left",
            wraplength=860,
        )
        self._erweitert_hinweis.pack(anchor="w", padx=8, pady=(0, 4))

        self._discovery_entry = ttk.Entry(erweitert_rahmen, width=38)
        self._discovery_entry.insert(0, "192.168.178.0/24")
        self._discovery_start_entry = ttk.Entry(erweitert_rahmen, width=6)
        self._discovery_start_entry.insert(0, "1")
        self._discovery_ende_entry = ttk.Entry(erweitert_rahmen, width=6)
        self._discovery_ende_entry.insert(0, "30")

        erweitert_felder = ttk.Frame(erweitert_rahmen)
        ttk.Label(erweitert_felder, text="Scanbereich:").pack(side="left")
        self._discovery_entry.pack(in_=erweitert_felder, side="left", padx=(4, 10))
        ttk.Label(erweitert_felder, text="Start:").pack(side="left")
        self._discovery_start_entry.pack(side="left", padx=(4, 8))
        ttk.Label(erweitert_felder, text="Ende:").pack(side="left")
        self._discovery_ende_entry.pack(side="left", padx=(4, 0))
        erweitert_felder.pack(anchor="w", padx=8, pady=(0, 8))
        self._setze_erweitert_felder_aktiv(False)

        ttk.Label(rahmen, text="Analyse-Reportpfad:").pack(anchor="w")
        ttk.Entry(rahmen, textvariable=self._analyse_pfad_var, width=55).pack(anchor="w", pady=(2, 10))

        schritte = ttk.Frame(rahmen)
        schritte.pack(fill="x", pady=(6, 10))
        schritte.columnconfigure((0, 1), weight=1)

        self._schritt_buttons["discovery"] = ttk.Button(schritte, text="1) Netzwerkerkennung starten", command=self.schritt_discovery)
        self._schritt_buttons["discovery"].grid(
            row=0, column=0, sticky="ew", padx=(0, 6), pady=4
        )
        self._schritt_buttons["rollen"] = ttk.Button(schritte, text="2) Rollen prüfen", command=self.schritt_rollen_pruefen)
        self._schritt_buttons["rollen"].grid(
            row=0, column=1, sticky="ew", padx=(6, 0), pady=4
        )
        self._schritt_buttons["analyse"] = ttk.Button(schritte, text="3) Analyse ausführen", command=self.schritt_analyse)
        self._schritt_buttons["analyse"].grid(
            row=1, column=0, sticky="ew", padx=(0, 6), pady=4
        )
        self._schritt_buttons["speichern"] = ttk.Button(
            schritte,
            text="4) Speichern/Bestätigen",
            command=self.schritt_speichern_und_abschliessen,
        )
        self._schritt_buttons["speichern"].grid(
            row=1, column=1, sticky="ew", padx=(6, 0), pady=4
        )

        self._baue_schrittstatus_anzeige(rahmen)
        self._aktualisiere_schritt_buttons()
        try:
            self._ermittle_automatischen_scanbereich()
        except ValueError as exc:
            self._setze_status(str(exc))

        # UI-Testplan:
        # 1) Auflösung 1366x768: Wizard öffnen, prüfen ob alle Elemente erreichbar sind
        #    (inkl. vertikalem Scrollen) und keine Bedienelemente abgeschnitten werden.
        # 2) Auflösung 1920x1080: Wizard öffnen, prüfen ob Layout ohne Scrollbar sauber
        #    ausgerichtet ist und Texte im erwarteten Umbruch dargestellt werden.
        ttk.Label(rahmen, textvariable=self._status_var, wraplength=900, justify="left").pack(anchor="w", pady=(8, 0))

    def schritt_discovery(self) -> None:
        """Schritt 1: Führt die Discovery durch und befüllt das Tabellenmodell."""
        if not self._ist_schritt_freigeschaltet("discovery"):
            return

        self._setze_aktuellen_schritt("discovery")

        try:
            discovery_bereiche, gespeicherte_eingabe = self._ermittle_discovery_bereiche_fuer_schritt_1()
        except ValueError as exc:
            self._markiere_schritt("discovery", "fehler", str(exc), "Netzkonfiguration prüfen oder erweiterten Pfad aktivieren.")
            self._setze_status(str(exc))
            return

        self._setze_status("Netzwerkerkennung läuft …")
        ergebnisse = []
        try:
            # Vorhandene Discovery-Pipeline bleibt unverändert nutzbar:
            # CIDR- oder Kurzformat-Eingaben werden intern auf Basis+Start/Ende gemappt.
            for basis, start, ende in discovery_bereiche:
                ergebnisse.extend(
                    entdecke_server_ergebnisse(
                        basis=basis,
                        start=start,
                        ende=ende,
                        konfiguration=DiscoveryKonfiguration(),
                    )
                )
        except Exception as exc:  # noqa: BLE001 - Wizard soll robust weiterlaufen.
            logger.exception("Netzwerkerkennung im Onboarding fehlgeschlagen")
            self._markiere_schritt(
                "discovery",
                "fehler",
                f"Netzwerkerkennung fehlgeschlagen: {exc}",
                "Berechtigungen, Firewall und Netzbereich prüfen.",
            )
            self._setze_status(f"Netzwerkerkennung fehlgeschlagen: {exc}")
            return

        self.server_zeilen = []
        for treffer in ergebnisse:
            # Die Rollenableitung wird identisch zur Discovery-Hauptmaske ausgeführt,
            # damit Onboarding und reguläre Erfassung dieselbe Heuristik teilen.
            rollen = ableite_rollen_aus_discoveryindikatoren(
                erkannte_dienste=treffer.erkannte_dienste,
                rollenhinweise=treffer.rollenhinweise,
                erreichbar=treffer.erreichbar,
            )

            self.server_zeilen.append(
                ServerTabellenZeile(
                    servername=treffer.hostname,
                    sql="SQL" in rollen,
                    app="APP" in rollen,
                    ctx="CTX" in rollen,
                    quelle="automatisch erkannt",
                    status="entdeckt",
                    auto_rolle=", ".join(rollen),
                    aufgeloester_hostname=treffer.hostname,
                    ip_adresse=treffer.ip_adresse,
                    namensquelle=treffer.namensquelle or "nicht auflösbar",
                    erreichbarkeitsstatus=formatiere_erreichbarkeitsstatus(
                        erreichbar=treffer.erreichbar,
                        vertrauensgrad=treffer.vertrauensgrad,
                    ),
                    vertrauensgrad=treffer.vertrauensgrad,
                    erreichbar=treffer.erreichbar,
                    rollenhinweise=tuple(treffer.rollenhinweise),
                )
            )

        self._discovery_bereiche = discovery_bereiche
        self._gespeicherter_scanbereich = gespeicherte_eingabe
        self.gui.modulzustand["letzte_discovery_range"] = gespeicherte_eingabe
        self._markiere_schritt(
            "discovery",
            "erfolgreich",
            f"{len(self.server_zeilen)} Server erkannt.",
            "Mit Schritt 2 Rollen prüfen und bei Bedarf anpassen.",
        )
        self._setze_status(f"Netzwerkerkennung abgeschlossen: {len(self.server_zeilen)} Server übernommen.")

    @staticmethod
    def _parse_discovery_eingabe(
        discovery_eingabe: str,
        start_eingabe: str,
        ende_eingabe: str,
    ) -> tuple[list[tuple[str, int, int]], str]:
        """Parst Eingaben der Netzwerkerkennung robust inkl. CIDR-Unterstützung.

        Unterstützte Eingaben:
        * CIDR (z. B. 192.168.0.0/24)
        * Basis + getrennte Start/Ende-Felder (z. B. 192.168.0 + 1/30)
        * Kurzformat in einem Feld (z. B. 192.168.0.1-30)
        """

        beispiel = "192.168.0.0/24 oder 192.168.0 + Start=1 und Ende=30 oder 192.168.0.1-30"
        if not discovery_eingabe:
            raise ValueError(f"Ungültige Eingabe für die Netzwerkerkennung. Beispiele: {beispiel}")

        if "/" in discovery_eingabe:
            try:
                netz = ipaddress.ip_network(discovery_eingabe, strict=False)
            except ValueError as exc:
                raise ValueError(f"Ungültiges CIDR-Format. Beispiele: {beispiel}") from exc
            if netz.version != 4:
                raise ValueError(f"Nur IPv4-CIDR wird unterstützt. Beispiele: {beispiel}")

            host_ips = [str(host) for host in netz.hosts()]
            if not host_ips:
                raise ValueError(f"CIDR-Bereich enthält keine nutzbaren Hosts. Beispiele: {beispiel}")

            # Gruppiert Hosts je /24-Basis und bildet daraus zusammenhängende Start/Ende-Bereiche,
            # damit die bestehende Discovery-Funktion ohne Umbau wiederverwendet werden kann.
            host_oktette = sorted((ip.split(".") for ip in host_ips), key=lambda teile: tuple(int(wert) for wert in teile))
            discovery_bereiche: list[tuple[str, int, int]] = []
            aktuelle_basis = ""
            start = ende = -1

            for teil_1, teil_2, teil_3, teil_4 in host_oktette:
                basis = f"{teil_1}.{teil_2}.{teil_3}"
                host = int(teil_4)

                if basis != aktuelle_basis or host != ende + 1:
                    if aktuelle_basis:
                        discovery_bereiche.append((aktuelle_basis, start, ende))
                    aktuelle_basis = basis
                    start = host
                    ende = host
                else:
                    ende = host

            discovery_bereiche.append((aktuelle_basis, start, ende))
            return discovery_bereiche, str(netz)

        kurzformat = re.fullmatch(r"(?P<basis>(?:\d{1,3}\.){2}\d{1,3})\.(?P<start>\d{1,3})-(?P<ende>\d{1,3})", discovery_eingabe)
        if kurzformat:
            basis = kurzformat.group("basis")
            start = int(kurzformat.group("start"))
            ende = int(kurzformat.group("ende"))
        else:
            basis = discovery_eingabe
            if not re.fullmatch(r"(?:\d{1,3}\.){2}\d{1,3}", basis):
                raise ValueError(f"Ungültiges Format für die Netzwerkerkennung (ehemals Discovery-Format). Beispiele: {beispiel}")
            if not start_eingabe or not ende_eingabe:
                raise ValueError(f"Start und Ende müssen gesetzt sein. Beispiele: {beispiel}")
            try:
                start = int(start_eingabe)
                ende = int(ende_eingabe)
            except ValueError as exc:
                raise ValueError(f"Start und Ende müssen ganze Zahlen sein. Beispiele: {beispiel}") from exc

        oktette = [int(wert) for wert in basis.split(".")]
        if any(oktett < 0 or oktett > 255 for oktett in oktette):
            raise ValueError(f"Ungültige IPv4-Basis. Beispiele: {beispiel}")
        if not (1 <= start <= 254 and 1 <= ende <= 254):
            raise ValueError(f"Start und Ende müssen zwischen 1 und 254 liegen. Beispiele: {beispiel}")
        if start > ende:
            raise ValueError(f"Start darf nicht größer als Ende sein. Beispiele: {beispiel}")

        return [(basis, start, ende)], f"{basis}.{start}-{ende}"

    def schritt_rollen_pruefen(self) -> None:
        """Schritt 2: Ermöglicht eine kontrollierte Mehrfach-Anpassung der Serverrollen."""
        if not self._ist_schritt_freigeschaltet("rollen"):
            return
        self._setze_aktuellen_schritt("rollen")

        if not self.server_zeilen:
            self._markiere_schritt(
                "rollen",
                "fehler",
                "Keine Serverdaten vorhanden.",
                "Zuerst Schritt 1 Netzwerkerkennung ausführen.",
            )
            self._setze_status("Keine Daten aus der Netzwerkerkennung vorhanden. Bitte zuerst Schritt 1 ausführen.")
            return

        dialog = tk.Toplevel(self._window)
        dialog.title("Rollenprüfung")
        dialog.geometry("1140x560")
        dialog.transient(self._window)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=(
                "Mehrfachauswahl: Nutzen Sie Strg+Klick für einzelne zusätzliche Server "
                "oder Umschalt+Klick für einen zusammenhängenden Bereich."
            ),
            wraplength=1080,
            justify="left",
        ).pack(fill="x", padx=10, pady=(10, 4))

        tree = ttk.Treeview(
            dialog,
            columns=("server", "hostname", "ip", "status", "rolle", "quelle"),
            show="headings",
            height=16,
            selectmode="extended",
        )
        tree.pack(fill="both", expand=True, padx=10, pady=(2, 6))
        tree.heading("server", text="Server")
        tree.heading("hostname", text="aufgelöster Hostname")
        tree.heading("ip", text="IP-Adresse")
        tree.heading("status", text="Erreichbarkeit/Vertrauen")
        tree.heading("rolle", text="Rolle")
        tree.heading("quelle", text="Quelle")
        tree.column("server", width=180)
        tree.column("hostname", width=230)
        tree.column("ip", width=130, anchor="center")
        tree.column("status", width=220)
        tree.column("rolle", width=120, anchor="center")
        tree.column("quelle", width=180)

        for index, zeile in enumerate(self.server_zeilen):
            rolle = "SQL" if zeile.sql else "CTX" if zeile.ctx else "APP"
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    zeile.servername,
                    zeile.aufgeloester_hostname or zeile.servername,
                    zeile.ip_adresse or "-",
                    zeile.erreichbarkeitsstatus or "unbekannt",
                    rolle,
                    zeile.quelle,
                ),
            )

        auswahl_geaendert_var = tk.BooleanVar(value=False)

        def rolle_setzen(rolle: str) -> None:
            ausgewaehlt = tree.selection()
            if not ausgewaehlt:
                self._setze_status("Keine Auswahl getroffen. Bitte mindestens einen Server markieren.")
                return

            for item_id in ausgewaehlt:
                zeile = self.server_zeilen[int(item_id)]
                vorher = "SQL" if zeile.sql else "CTX" if zeile.ctx else "APP"
                zeile.sql = rolle == "SQL"
                zeile.app = rolle == "APP"
                zeile.ctx = rolle == "CTX"
                zeile.manuell_ueberschrieben = vorher != rolle
                zeile.status = "rolle geprüft"
                tree.set(item_id, "rolle", rolle)
                if zeile.manuell_ueberschrieben:
                    zeile.quelle = "manuell angepasst"
                elif zeile.quelle.lower() != "manuell angepasst":
                    zeile.quelle = "automatisch erkannt"
                tree.set(item_id, "quelle", zeile.quelle)

            auswahl_geaendert_var.set(True)

        def alle_markieren() -> None:
            tree.selection_set(tree.get_children(""))

        def keine_markieren() -> None:
            tree.selection_remove(tree.selection())

        def abbrechen() -> None:
            dialog.destroy()
            self._setze_status("Rollenprüfung abgebrochen. Änderungen wurden nicht bestätigt.")

        def uebernehmen() -> None:
            dialog.destroy()
            self._markiere_schritt(
                "rollen",
                "erfolgreich",
                f"{len(self.server_zeilen)} Serverrollen bestätigt.",
                "Nach Prüfung Schritt 3 Analyse ausführen.",
            )
            if auswahl_geaendert_var.get():
                self._setze_status("Rollenprüfung abgeschlossen und manuelle Anpassungen übernommen.")
            else:
                self._setze_status("Rollenprüfung abgeschlossen: Rollen unverändert bestätigt.")

        button_rahmen = ttk.Frame(dialog)
        button_rahmen.pack(fill="x", padx=10, pady=(0, 10))

        for rolle in ("SQL", "APP", "CTX"):
            ttk.Button(button_rahmen, text=f"Als {rolle} markieren", command=lambda r=rolle: rolle_setzen(r)).pack(
                side="left", padx=4
            )

        ttk.Separator(button_rahmen, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(button_rahmen, text="Alle markieren", command=alle_markieren).pack(side="left", padx=4)
        ttk.Button(button_rahmen, text="Keine", command=keine_markieren).pack(side="left", padx=4)

        ttk.Button(button_rahmen, text="Abbrechen", command=abbrechen).pack(side="right", padx=4)
        ttk.Button(button_rahmen, text="Übernehmen (OK)", command=uebernehmen).pack(side="right", padx=4)

        self._setze_status("Rollenprüfung geöffnet: Mehrfachauswahl und Rollenanpassung verfügbar.")

    def schritt_analyse(self) -> None:
        """Schritt 3: Startet die Analyse auf Basis der bestätigten Rollen."""
        if not self._ist_schritt_freigeschaltet("analyse"):
            return
        self._setze_aktuellen_schritt("analyse")

        if not self.server_zeilen:
            self._markiere_schritt(
                "analyse",
                "fehler",
                "Keine Server vorhanden.",
                "Schritt 1 und 2 vollständig durchführen.",
            )
            self._setze_status("Keine Server vorhanden. Netzwerkerkennung und Rollenprüfung zuerst ausführen.")
            return

        ziele = _baue_serverziele(self.server_zeilen)
        if not ziele:
            self._markiere_schritt(
                "analyse",
                "fehler",
                "Keine gültigen Analyseziele erzeugt.",
                "Rollenprüfung erneut öffnen und Eingaben kontrollieren.",
            )
            self._setze_status("Es konnten keine gültigen Analyseziele aus dem Tabellenmodell erzeugt werden.")
            return

        self._setze_status("Analyse läuft …")
        try:
            self.analyse_ergebnisse = analysiere_mehrere_server(ziele)
        except Exception as exc:  # noqa: BLE001 - Wizard zeigt Fehler im UI an.
            logger.exception("Analyse im Onboarding fehlgeschlagen")
            self._markiere_schritt("analyse", "fehler", f"Analyse fehlgeschlagen: {exc}", "Zielserver-Erreichbarkeit prüfen.")
            self._setze_status(f"Analyse fehlgeschlagen: {exc}")
            return

        # Manuelle Ergänzungen werden direkt in die Analyseobjekte integriert,
        # damit der Zustand konsistent für Persistenz und Reporting bleibt.
        _integriere_manuelle_anmerkungen(self.analyse_ergebnisse, self.server_zeilen)

        status_index = {normalisiere_servernamen(e.server): "analysiert" for e in self.analyse_ergebnisse}
        for zeile in self.server_zeilen:
            zeile.status = status_index.get(normalisiere_servernamen(zeile.servername), "nicht analysiert")

        self._oeffne_bearbeitungsansicht_nach_analyse()

        self._markiere_schritt(
            "analyse",
            "erfolgreich",
            f"{len(self.analyse_ergebnisse)} Server analysiert.",
            "Mit Schritt 4 Ergebnisse speichern und bestätigen.",
        )
        self._setze_status(f"Analyse abgeschlossen: {len(self.analyse_ergebnisse)} Server analysiert.")

    def _oeffne_bearbeitungsansicht_nach_analyse(self) -> None:
        """Bietet nach der Analyse je Server eine gezielte Nachbearbeitung inkl. Freitext an."""
        if not self.analyse_ergebnisse:
            return

        dialog = tk.Toplevel(self._window)
        dialog.title("Bearbeitungsansicht nach Analyse")
        dialog.geometry("1180x620")
        dialog.transient(self._window)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="Manuelle Ergänzungen (optional), damit projektspezifische Infos nicht verloren gehen.",
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(10, 6))

        tree = ttk.Treeview(
            dialog,
            columns=("server", "rollen", "ports", "status", "anmerkung"),
            show="headings",
            height=18,
        )
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        tree.heading("server", text="Server")
        tree.heading("rollen", text="Erkannte Rollen")
        tree.heading("ports", text="Offene Ports")
        tree.heading("status", text="Status")
        tree.heading("anmerkung", text="Anmerkungen/Besonderheiten")
        tree.column("server", width=170)
        tree.column("rollen", width=180)
        tree.column("ports", width=180)
        tree.column("status", width=120, anchor="center")
        tree.column("anmerkung", width=480)

        zeilenindex = {normalisiere_servernamen(zeile.servername): zeile for zeile in self.server_zeilen}

        for ergebnis in self.analyse_ergebnisse:
            norm_name = normalisiere_servernamen(ergebnis.server)
            zeile = zeilenindex.get(norm_name)
            rollen = ", ".join(ergebnis.rollen) or "keine Rolle"
            offene_ports = ", ".join(str(port.port) for port in ergebnis.ports if port.offen) or "keine"
            status = "erreichbar" if any(port.offen for port in ergebnis.ports) else "nicht erreichbar"
            anmerkung = (zeile.manuelle_anmerkung if zeile else ergebnis.manuelle_anmerkung).strip()
            tree.insert("", "end", iid=norm_name, values=(ergebnis.server, rollen, offene_ports, status, anmerkung))

        anmerkung_var = tk.StringVar(value="")
        ttk.Label(dialog, text="Anmerkungen/Besonderheiten:").pack(anchor="w", padx=10)
        eintrag = ttk.Entry(dialog, textvariable=anmerkung_var, width=120)
        eintrag.pack(fill="x", padx=10, pady=(0, 8))

        def auswahl_uebernehmen(_event: tk.Event[tk.Misc] | None = None) -> None:
            auswahl = tree.selection()
            if not auswahl:
                anmerkung_var.set("")
                return
            anmerkung_var.set(str(tree.set(auswahl[0], "anmerkung") or ""))

        def anmerkung_speichern() -> None:
            auswahl = tree.selection()
            if not auswahl:
                self._setze_status("Bitte zuerst einen Server in der Bearbeitungsansicht auswählen.")
                return

            item_id = auswahl[0]
            neue_anmerkung = anmerkung_var.get().strip()
            tree.set(item_id, "anmerkung", neue_anmerkung)

            for zeile in self.server_zeilen:
                if normalisiere_servernamen(zeile.servername) == item_id:
                    zeile.manuelle_anmerkung = neue_anmerkung
                    break

            for ergebnis in self.analyse_ergebnisse:
                if normalisiere_servernamen(ergebnis.server) != item_id:
                    continue
                bisherige_anmerkung = ergebnis.manuelle_anmerkung.strip()
                ergebnis.hinweise = [
                    hinweis
                    for hinweis in ergebnis.hinweise
                    if hinweis.strip() and hinweis.strip() != bisherige_anmerkung
                ]
                ergebnis.manuelle_anmerkung = neue_anmerkung
                if neue_anmerkung:
                    ergebnis.hinweise.append(neue_anmerkung)
                break

            self._setze_status("Anmerkung gespeichert und in den Analysezustand übernommen.")

        tree.bind("<<TreeviewSelect>>", auswahl_uebernehmen)

        button_rahmen = ttk.Frame(dialog)
        button_rahmen.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(button_rahmen, text="Anmerkung übernehmen", command=anmerkung_speichern).pack(side="left")
        ttk.Button(button_rahmen, text="Fertig", command=dialog.destroy).pack(side="right")

    def schritt_speichern_und_abschliessen(self) -> None:
        """Schritt 4: Persistiert Moduldaten + Onboarding-Status atomar im Gesamtzustand."""
        if not self._ist_schritt_freigeschaltet("speichern"):
            return
        self._setze_aktuellen_schritt("speichern")

        if not self.server_zeilen:
            self._markiere_schritt(
                "speichern",
                "fehler",
                "Keine Daten zum Speichern vorhanden.",
                "Vorher mindestens Schritt 1 durchführen.",
            )
            self._setze_status("Es gibt keine Daten zum Speichern. Bitte vorher Schritt 1 ausführen.")
            return

        try:
            # Persistenzlogik der Serveranalyse zentral über einen datenbasierten Service ausführen.
            self._speichere_serveranalyse_zustand_ueber_gui_methode()

            onboarding_status = self.state_store.lade_onboarding_status()
            now_iso = datetime.now().isoformat(timespec="seconds")
            onboarding_status.update(
                {
                    "onboarding_abgeschlossen": True,
                    "onboarding_status": "abgeschlossen",
                    "onboarding_version": _ONBOARDING_VERSION,
                    "erststart_zeitpunkt": onboarding_status.get("erststart_zeitpunkt") or now_iso,
                    "letzter_abschluss_zeitpunkt": now_iso,
                    "abbruch_zeitpunkt": "",
                }
            )

            gesamtzustand = self.state_store.lade_gesamtzustand()
            gesamtzustand["onboarding"] = onboarding_status
            self.state_store.speichere_gesamtzustand(gesamtzustand)

            self.gui.modulzustand = self.state_store.lade_modulzustand("gui_manager")
            self.gui.aktiviere_dashboardmodus_nach_onboarding()
        except Exception as exc:  # noqa: BLE001 - Benutzer bekommt einen klaren Dialog statt stiller Ausnahme.
            logger.exception("Onboarding-Schritt 'Speichern/Bestätigen' fehlgeschlagen")
            self._markiere_schritt(
                "speichern",
                "fehler",
                "Speichern fehlgeschlagen.",
                "Eingaben prüfen und Schritt erneut starten.",
            )
            self._setze_status(f"Speichern fehlgeschlagen: {exc}")
            messagebox.showerror(
                "Speichern fehlgeschlagen",
                (
                    "Die Daten konnten nicht vollständig gespeichert werden.\n\n"
                    f"Technischer Hinweis: {exc}\n\n"
                    "Bitte prüfen Sie Eingaben/Dateirechte und versuchen Sie es erneut."
                ),
                parent=self._window,
            )
            return

        self._markiere_schritt(
            "speichern",
            "erfolgreich",
            "Onboarding vollständig gespeichert.",
            "Dashboard kann nun regulär verwendet werden.",
        )
        self._setze_status("Onboarding abgeschlossen und vollständig gespeichert.")
        messagebox.showinfo(
            "Erststart abgeschlossen",
            "Der Erststart wurde erfolgreich abgeschlossen. Das Dashboard kann jetzt regulär genutzt werden.",
            parent=self._window,
        )
        if self._window:
            self._window.destroy()

    def _speichere_serveranalyse_zustand_ueber_gui_methode(self) -> None:
        """Persistiert Onboarding-Ergebnisse über eine UI-unabhängige Service-Funktion."""
        modulzustand_serveranalyse = self.state_store.lade_modulzustand("server_analysis")
        discovery_eingabe = modulzustand_serveranalyse.get("letzte_discovery_eingabe", {})

        persistenzdaten = ServerAnalysePersistenzDaten(
            serverlisten=[zeile.__dict__.copy() for zeile in self.server_zeilen],
            rollen={zeile.servername: zeile.rollen() for zeile in self.server_zeilen},
            letzte_discovery_range=self.gui.modulzustand.get("letzte_discovery_range", "").strip(),
            letzter_discovery_modus=str(modulzustand_serveranalyse.get("letzter_discovery_modus", "range") or "range").strip(),
            letzte_discovery_namen=str(modulzustand_serveranalyse.get("letzte_discovery_namen", "") or "").strip(),
            letzte_discovery_eingabe={
                "basis": str(discovery_eingabe.get("basis", "") or "").strip(),
                "start": str(discovery_eingabe.get("start", "") or "").strip(),
                "ende": str(discovery_eingabe.get("ende", "") or "").strip(),
            },
            ausgabepfade={
                "analyse_report": (self._analyse_pfad_var.get().strip() if self._analyse_pfad_var else "docs/serverbericht.md")
                or "docs/serverbericht.md",
                "log_report": "logs/log_dokumentation.md",
            },
            server_summary=_baue_server_summary(self.analyse_ergebnisse),
            letzte_kerninfos=[
                f"Analyse-Status: {len(self.server_zeilen)} Server zuletzt geprüft.",
                "Server-Status: " + _formatiere_server_summary_fuer_dashboard(_baue_server_summary(self.analyse_ergebnisse), limit=5),
                f"Netzwerkerkennungs-Bereich: {self.gui.modulzustand.get('letzte_discovery_range', '').strip() or 'nicht gesetzt'}",
            ],
            bericht_verweise=[
                (self._analyse_pfad_var.get().strip() if self._analyse_pfad_var else "docs/serverbericht.md") or "docs/serverbericht.md",
                "logs/log_dokumentation.md",
            ],
            letzter_exportpfad=str(modulzustand_serveranalyse.get("letzter_exportpfad", "") or ""),
            letzter_exportzeitpunkt=str(modulzustand_serveranalyse.get("letzter_exportzeitpunkt", "") or ""),
            letzte_export_lauf_id=str(modulzustand_serveranalyse.get("letzte_export_lauf_id", "") or ""),
        )
        persistiere_serveranalyse_zustand(
            state_store=self.state_store,
            modulzustand=modulzustand_serveranalyse,
            daten=persistenzdaten,
            shell=None,
        )

        # Synchronisiere die wichtigsten Übersichtsdaten zusätzlich mit dem Launcher-Modul.
        self.gui.modulzustand.setdefault("letzte_kerninfos", [])
        self.gui.modulzustand["letzte_kerninfos"] = [
            f"Onboarding abgeschlossen: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Server in Ersterfassung: {len(self.server_zeilen)}",
        ]
        self.gui.modulzustand.setdefault("bericht_verweise", [])
        analyse_report = persistenzdaten.ausgabepfade["analyse_report"]
        self.gui.modulzustand["bericht_verweise"] = [analyse_report]
        self.state_store.speichere_modulzustand("gui_manager", self.gui.modulzustand)

    def _abbrechen(self) -> None:
        """Bricht das Onboarding kontrolliert mit expliziter Benutzerbestätigung ab."""
        if not messagebox.askyesno(
            "Onboarding wirklich abbrechen?",
            (
                "Möchten Sie den Erststart wirklich abbrechen?\n\n"
                "Ja = Abbrechen und Anwendung schließen\n"
                "Nein = Im Assistenten bleiben"
            ),
            parent=self._window,
            icon="warning",
        ):
            self._setze_status("Onboarding wird fortgesetzt.")
            return

        abbruch_zeitpunkt = datetime.now().isoformat(timespec="seconds")
        self.state_store.speichere_onboarding_status(
            {
                "onboarding_abgeschlossen": False,
                "onboarding_status": "abgebrochen",
                "abbruch_zeitpunkt": abbruch_zeitpunkt,
            }
        )

        abbruch_aktion = self.gui.onboarding_abbruch_aktion
        self._setze_status(f"Erststart abgebrochen: Aktion '{abbruch_aktion}' wird ausgeführt.")
        if self._window:
            self._window.destroy()

        if abbruch_aktion == "app_schliessen":
            self.gui.master.after(50, self.gui.master.quit)

    def _setze_status(self, text: str) -> None:
        """Aktualisiert die Wizard-Statuszeile zentral und robust."""
        if self._status_var is not None:
            self._status_var.set(text)
        logger.info("[Onboarding] %s", text)

    def _baue_schrittstatus_anzeige(self, parent: ttk.Frame) -> None:
        """Zeigt pro Onboarding-Schritt den Zustand und die nächste Aktion an."""
        status_rahmen = ttk.LabelFrame(parent, text="Schrittstatus", style="Section.TLabelframe")
        status_rahmen.pack(fill="x", pady=(2, 10))

        for index, schritt in enumerate(self._schritt_reihenfolge, start=1):
            status_var = tk.StringVar(value="Wartet")
            aktion_var = tk.StringVar(value="Noch keine Aktion erforderlich.")
            self._schritt_status_var[schritt] = status_var
            self._schritt_aktion_var[schritt] = aktion_var

            ttk.Label(status_rahmen, text=f"{index}.").grid(row=index - 1, column=0, sticky="nw", padx=(8, 6), pady=3)
            ttk.Label(status_rahmen, text=self._titel_fuer_schritt(schritt)).grid(row=index - 1, column=1, sticky="w", pady=3)
            ttk.Label(status_rahmen, textvariable=status_var).grid(row=index - 1, column=2, sticky="w", padx=(10, 8), pady=3)
            ttk.Label(status_rahmen, textvariable=aktion_var, wraplength=340, justify="left").grid(
                row=index - 1,
                column=3,
                sticky="w",
                padx=(0, 8),
                pady=3,
            )

        self._markiere_schritt(
            "discovery",
            "aktiv",
            "Aktueller Schritt",
            "Netzwerkerkennung starten, um den Ablauf zu beginnen.",
            auto_freigabe=False,
        )

    def _titel_fuer_schritt(self, schritt: str) -> str:
        titel = {
            "discovery": "Netzwerkerkennung",
            "rollen": "Rollen prüfen",
            "analyse": "Analyse ausführen",
            "speichern": "Speichern/Bestätigen",
        }
        return titel.get(schritt, schritt)

    def _markiere_schritt(
        self,
        schritt: str,
        status: str,
        meldung: str,
        empfohlene_aktion: str,
        *,
        auto_freigabe: bool = True,
    ) -> None:
        """Pflegt den sichtbaren Schrittstatus einheitlich und schaltet Folge-Schritte frei."""
        status_texte = {
            "wartet": "Wartet",
            "aktiv": "Aktiv",
            "erfolgreich": "Erfolgreich",
            "fehler": "Fehlerhaft",
        }
        status_label = status_texte.get(status, status)
        self._schritt_status_var[schritt].set(f"{status_label}: {meldung}")
        self._schritt_aktion_var[schritt].set(f"Empfehlung: {empfohlene_aktion}")

        if auto_freigabe and status == "erfolgreich":
            self._freigeschalteter_schritt_index = max(self._freigeschalteter_schritt_index, self._schritt_position[schritt] + 1)
            self._aktualisiere_schritt_buttons()

    def _setze_aktuellen_schritt(self, schritt: str) -> None:
        """Markiert den aktuell bearbeiteten Schritt in der Statusanzeige."""
        self._aktueller_schritt = schritt
        self._markiere_schritt(schritt, "aktiv", "Aktueller Schritt", "Aktion ausführen und Ergebnis prüfen.", auto_freigabe=False)

    def _ist_schritt_freigeschaltet(self, schritt: str) -> bool:
        """Prüft die Reihenfolge im geführten Standardfluss."""
        if self._schritt_position[schritt] > self._freigeschalteter_schritt_index:
            self._setze_status("Bitte die vorherigen Schritte im geführten Ablauf zuerst abschließen.")
            return False
        return True

    def _aktualisiere_schritt_buttons(self) -> None:
        """Aktiviert Buttons nur gemäß aktueller Schrittfreigabe."""
        for schritt, button in self._schritt_buttons.items():
            status = "normal" if self._schritt_position[schritt] <= self._freigeschalteter_schritt_index else "disabled"
            button.configure(state=status)

    def _umschalten_erweiterten_pfad(self) -> None:
        """Aktiviert den optionalen erweiterten Scanpfad erst nach Bestätigung."""
        if self._erweitert_aktiv_var is None:
            return

        if not self._erweitert_aktiv_var.get():
            self._setze_erweitert_felder_aktiv(False)
            self._setze_status("Erweiterter Pfad deaktiviert. Standardfluss bleibt aktiv.")
            return

        bestaetigt = messagebox.askyesno(
            "Erweiterten Pfad bestätigen",
            "Der erweiterte Pfad erlaubt manuelle Scanbereiche und kann zu längeren Laufzeiten führen. Fortfahren?",
            parent=self._window,
        )
        if not bestaetigt:
            self._erweitert_aktiv_var.set(False)
            self._setze_erweitert_felder_aktiv(False)
            return

        self._setze_erweitert_felder_aktiv(True)
        self._setze_status("Erweiterter Pfad aktiviert: optionaler manueller Netzscanbereich freigeschaltet.")

    def _setze_erweitert_felder_aktiv(self, aktiv: bool) -> None:
        """Steuert die Eingabefelder des optionalen erweiterten Pfads."""
        state = "normal" if aktiv else "disabled"
        for feld in (self._discovery_entry, self._discovery_start_entry, self._discovery_ende_entry):
            feld.configure(state=state)

    def _ermittle_discovery_bereiche_fuer_schritt_1(self) -> tuple[list[tuple[str, int, int]], str]:
        """Liefert Discovery-Bereiche für Schritt 1 aus Standard- oder erweitertem Pfad."""
        if self._erweitert_aktiv_var and self._erweitert_aktiv_var.get():
            discovery_eingabe = self._discovery_entry.get().strip() if self._window else ""
            start_eingabe = self._discovery_start_entry.get().strip() if self._window else ""
            ende_eingabe = self._discovery_ende_entry.get().strip() if self._window else ""
            return self._parse_discovery_eingabe(discovery_eingabe, start_eingabe, ende_eingabe)
        return self._ermittle_automatischen_scanbereich()

    def _ermittle_automatischen_scanbereich(self) -> tuple[list[tuple[str, int, int]], str]:
        """Leitet den Standard-Scanbereich aus lokaler IPv4-Konfiguration ab."""
        for ip_text, maske_text in self._sammle_lokale_ipv4_konfigurationen():
            try:
                interface = ipaddress.IPv4Interface(f"{ip_text}/{maske_text}")
            except ValueError:
                continue

            netz = interface.network
            if netz.num_addresses < 4:
                continue

            erster_host = ipaddress.IPv4Address(int(netz.network_address) + 1)
            letzter_host = ipaddress.IPv4Address(int(netz.broadcast_address) - 1)
            basis = ".".join(str(erster_host).split(".")[:3])
            start = int(str(erster_host).split(".")[3])
            ende = int(str(letzter_host).split(".")[3])

            if netz.prefixlen < 24:
                start, ende = 1, 254

            gespeicherter_bereich = f"{basis}.{start}-{ende}"
            if self._scanbereich_var is not None:
                self._scanbereich_var.set(f"{netz} (abgeleitet aus {ip_text}/{maske_text})")
            return [(basis, start, ende)], gespeicherter_bereich

        raise ValueError("Kein geeigneter lokaler IPv4-Netzbereich gefunden. Bitte erweiterten Pfad verwenden.")

    @staticmethod
    def _sammle_lokale_ipv4_konfigurationen() -> list[tuple[str, str]]:
        """Sammelt lokale IPv4- und Subnetzmasken-Kombinationen plattformunabhängig."""
        konfigurationen: list[tuple[str, str]] = []

        # Linux/macOS: direkte Auswertung der Interface-Adressen via `ip`.
        if os.name != "nt":
            try:
                output = subprocess.check_output(["ip", "-o", "-f", "inet", "addr", "show"], text=True, stderr=subprocess.STDOUT)
                for zeile in output.splitlines():
                    teile = zeile.split()
                    if "inet" not in teile:
                        continue
                    inet_index = teile.index("inet")
                    cidr = teile[inet_index + 1]
                    ip_text, prefix = cidr.split("/")
                    if ip_text.startswith("127."):
                        continue
                    maske = str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)
                    konfigurationen.append((ip_text, maske))
            except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
                pass

        # Windows-Fallback: `ipconfig` liefert IPv4 und Subnetzmaske pro Adapterblock.
        try:
            output = subprocess.check_output(["ipconfig"], text=True, stderr=subprocess.STDOUT)
            aktuelle_ip = ""
            for zeile in output.splitlines():
                if "IPv4" in zeile:
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", zeile)
                    if match:
                        aktuelle_ip = match.group(1)
                elif "Subnetzmaske" in zeile or "Subnet Mask" in zeile:
                    mask_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", zeile)
                    if aktuelle_ip and mask_match and not aktuelle_ip.startswith("127."):
                        konfigurationen.append((aktuelle_ip, mask_match.group(1)))
                        aktuelle_ip = ""
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return konfigurationen


class SystemManagerGUI:
    """Kapselt Aufbau und Verhalten der Launcher-Oberfläche."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.geometry("1080x820")

        self.state_store = GUIStateStore()
        self.modulzustand = self.state_store.lade_modulzustand("gui_manager")
        # Deployment-spezifische Abbruchrichtlinie: modulzustand > onboarding-status > Standard.
        self.onboarding_abbruch_aktion = str(
            self.modulzustand.get("onboarding_abbruch_aktion")
            or self.state_store.lade_onboarding_status().get("onboarding_abbruch_aktion")
            or _STANDARD_ONBOARDING_ABBRUCH_AKTION
        ).strip() or _STANDARD_ONBOARDING_ABBRUCH_AKTION
        self.onboarding_status = self._initialisiere_onboarding_status()
        self._onboarding_aktiv = not self.onboarding_status.get("onboarding_abgeschlossen", False)

        untertitel = (
            "Geführter Erststart: Bitte den Assistenten vollständig abschließen"
            if self._onboarding_aktiv
            else "Zentrale Modulübersicht für Analyse, Ordnerverwaltung und Dokumentation"
        )
        self.shell = GuiShell(
            master,
            titel="SystemManager-SageHelper",
            untertitel=untertitel,
            on_save=self.speichern,
            on_back=self.zurueck,
            on_exit=self.master.quit,
            show_actions=not self._onboarding_aktiv,
        )

        self._karten_status: dict[str, tk.StringVar] = {}
        self._karten_buttons: dict[str, ttk.Button] = {}
        self._karten_titel: dict[str, tk.StringVar] = {}
        self._karten_beschreibung: dict[str, tk.StringVar] = {}
        self._karten_experten_buttons: dict[str, ttk.Button] = {}
        self._karten_technische_details: dict[str, tk.StringVar] = {}
        self._serversektion_eingeklappt = tk.BooleanVar(value=False)
        self._serversektion_toggle_text = tk.StringVar(value="▾ Übernommene Server")
        self._serverdetail_vars: dict[str, tk.StringVar] = {}
        self._serveransicht_index: dict[str, dict[str, object]] = {}
        self._dashboard_gebaut = False
        self._onboarding_controller = OnboardingController(self)

        if self._onboarding_aktiv:
            # Während des Erststarts ist bewusst kein parallel nutzbares Dashboard sichtbar.
            self.shell.setze_status("Erststart erkannt: Dashboard gesperrt, Assistent wird geöffnet")
        else:
            self._baue_dashboard()
            self._dashboard_gebaut = True

        self._pruefe_onboarding_guard()

    def _initialisiere_onboarding_status(self) -> dict[str, object]:
        """Lädt den Onboardingstatus und ergänzt fehlende Erststartdaten robust."""
        onboarding_status = self.state_store.lade_onboarding_status()
        if not onboarding_status.get("erststart_zeitpunkt"):
            onboarding_status["erststart_zeitpunkt"] = datetime.now().isoformat(timespec="seconds")
            onboarding_status["onboarding_version"] = onboarding_status.get("onboarding_version") or _ONBOARDING_VERSION
            onboarding_status.setdefault("onboarding_status", "ausstehend")
            onboarding_status["onboarding_abbruch_aktion"] = getattr(
                self,
                "onboarding_abbruch_aktion",
                _STANDARD_ONBOARDING_ABBRUCH_AKTION,
            )
            self.state_store.speichere_onboarding_status(onboarding_status)
            return onboarding_status

        onboarding_status.setdefault(
            "onboarding_abbruch_aktion",
            getattr(self, "onboarding_abbruch_aktion", _STANDARD_ONBOARDING_ABBRUCH_AKTION),
        )
        return onboarding_status

    def _pruefe_onboarding_guard(self) -> None:
        """Startet beim Erststart automatisch den geführten Wizard."""
        if self._onboarding_aktiv:
            self.master.after(150, self._onboarding_controller.starte_wizard)

    def aktiviere_dashboardmodus_nach_onboarding(self) -> None:
        """Aktiviert das Hauptdashboard explizit nach erfolgreichem Onboarding."""
        self._onboarding_aktiv = False
        self.onboarding_status = self.state_store.lade_onboarding_status()
        if not self._dashboard_gebaut:
            self._baue_dashboard()
            self._dashboard_gebaut = True
        self.shell.setze_status("Onboarding abgeschlossen: Dashboard wurde freigeschaltet")

    def _baue_dashboard(self) -> None:
        """Erzeugt die Startseite mit klaren Modul-Cards inklusive Statusanzeige."""
        dashboard = ttk.LabelFrame(self.shell.content_frame, text="Startübersicht", style="Section.TLabelframe")
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

        self._baue_serversektion(dashboard, start_zeile=2)

        cards = ttk.Frame(dashboard)
        cards.grid(row=3, column=0, sticky="ew", padx=LAYOUT.padding_inline, pady=(0, 12))
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

    def _baue_serversektion(self, parent: ttk.LabelFrame, *, start_zeile: int) -> None:
        """Erstellt eine einklappbare Übersicht über übernommene Server.

        Die Tabelle kombiniert Analyse-Snapshots (`server_summary`) mit
        Discovery-Metadaten aus der Modulpersistenz (`serverlisten`).
        """
        toggle_button = ttk.Button(parent, textvariable=self._serversektion_toggle_text, command=self._toggle_serversektion)
        toggle_button.grid(
            row=start_zeile,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=LAYOUT.padding_inline,
            pady=(0, 6),
        )

        self._serversektion_frame = ttk.Frame(parent)
        self._serversektion_frame.grid(
            row=start_zeile + 1,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=LAYOUT.padding_inline,
            pady=(0, 10),
        )

        tabellenrahmen = ttk.Frame(self._serversektion_frame)
        tabellenrahmen.pack(fill="x", expand=False)

        spalten = ("server", "fqdn", "ip", "reach", "rollen", "quelle", "analyse")
        self.server_uebersicht = ttk.Treeview(tabellenrahmen, columns=spalten, show="headings", height=6)
        self.server_uebersicht.pack(side="left", fill="x", expand=True)

        self.server_uebersicht.heading("server", text="Servername")
        self.server_uebersicht.heading("fqdn", text="FQDN/Hostname")
        self.server_uebersicht.heading("ip", text="IP")
        self.server_uebersicht.heading("reach", text="Erreichbarkeit/Vertrauen")
        self.server_uebersicht.heading("rollen", text="Rolle(n)")
        self.server_uebersicht.heading("quelle", text="Rollenquelle")
        self.server_uebersicht.heading("analyse", text="Letzte Analyse")

        self.server_uebersicht.column("server", width=140)
        self.server_uebersicht.column("fqdn", width=210)
        self.server_uebersicht.column("ip", width=120, anchor="center")
        self.server_uebersicht.column("reach", width=220)
        self.server_uebersicht.column("rollen", width=150)
        self.server_uebersicht.column("quelle", width=150)
        self.server_uebersicht.column("analyse", width=160)

        scrollbar = ttk.Scrollbar(tabellenrahmen, orient="vertical", command=self.server_uebersicht.yview)
        scrollbar.pack(side="right", fill="y")
        self.server_uebersicht.configure(yscrollcommand=scrollbar.set)
        self.server_uebersicht.bind("<<TreeviewSelect>>", self._bei_serverauswahl)

        details = ttk.LabelFrame(self._serversektion_frame, text="Server-Details", style="Section.TLabelframe")
        details.pack(fill="x", pady=(8, 0))
        details.columnconfigure(1, weight=1)

        for index, (schluessel, label) in enumerate(
            [
                ("betriebssystem", "Betriebssystem"),
                ("dienste", "Dienste"),
                ("ports", "Ports"),
                ("hinweise", "Hinweise"),
            ]
        ):
            self._serverdetail_vars[schluessel] = tk.StringVar(value="-")
            ttk.Label(details, text=f"{label}:", width=18).grid(row=index, column=0, sticky="nw", padx=8, pady=4)
            ttk.Label(
                details,
                textvariable=self._serverdetail_vars[schluessel],
                justify="left",
                wraplength=860,
            ).grid(row=index, column=1, sticky="ew", padx=(0, 8), pady=4)

        self._lade_serversektion()

    def _toggle_serversektion(self) -> None:
        """Klappsteuerung für die kompakte Serversektion."""
        ist_eingeklappt = not self._serversektion_eingeklappt.get()
        self._serversektion_eingeklappt.set(ist_eingeklappt)
        if ist_eingeklappt:
            self._serversektion_frame.grid_remove()
            self._serversektion_toggle_text.set("▸ Übernommene Server")
        else:
            self._serversektion_frame.grid()
            self._serversektion_toggle_text.set("▾ Übernommene Server")

    def _baue_serveransicht_zeilen(self, module: dict[str, object]) -> list[dict[str, object]]:
        """Konsolidiert Server-Snapshot und Discovery-Metadaten in ein UI-Modell."""
        serveranalyse_modul = module.get("server_analysis", {})
        if not isinstance(serveranalyse_modul, dict):
            return []

        server_summary = serveranalyse_modul.get("server_summary", [])
        discovery_liste = serveranalyse_modul.get("serverlisten", [])

        summary_liste = server_summary if isinstance(server_summary, list) else []
        discovery_index: dict[str, dict[str, object]] = {}
        if isinstance(discovery_liste, list):
            for discovery in discovery_liste:
                if not isinstance(discovery, dict):
                    continue
                name = str(discovery.get("servername") or "").strip()
                if name:
                    discovery_index[normalisiere_servernamen(name)] = discovery

        zeilen: list[dict[str, object]] = []
        for summary in summary_liste:
            if not isinstance(summary, dict):
                continue
            servername = str(summary.get("name") or "").strip()
            if not servername:
                continue
            discovery = discovery_index.get(normalisiere_servernamen(servername), {})
            rollen_liste = summary.get("rollen", [])
            rollen = ", ".join(rollen_liste) if isinstance(rollen_liste, list) and rollen_liste else "keine Rolle"

            erreichbarkeit = str(discovery.get("erreichbarkeitsstatus") or "").strip()
            if not erreichbarkeit:
                erreichbarkeit = "erreichbar" if bool(summary.get("erreichbar")) else "nicht erreichbar"
            vertrauensgrad = discovery.get("vertrauensgrad")
            if isinstance(vertrauensgrad, (int, float)):
                erreichbarkeit = f"{erreichbarkeit} ({float(vertrauensgrad):.2f})"

            hinweise_liste = summary.get("hinweise") if isinstance(summary.get("hinweise"), list) else []
            manuelle_anmerkung = str(summary.get("manuelle_anmerkung") or "").strip()
            if manuelle_anmerkung and manuelle_anmerkung not in hinweise_liste:
                hinweise_liste = [*hinweise_liste, manuelle_anmerkung]

            zeilen.append(
                {
                    "servername": servername,
                    "fqdn": str(
                        discovery.get("aufgeloester_hostname")
                        or summary.get("fqdn")
                        or summary.get("hostname")
                        or servername
                    ),
                    "ip": str(discovery.get("ip_adresse") or summary.get("ip") or "-"),
                    "reach": erreichbarkeit,
                    "rollen": rollen,
                    "rollenquelle": str(summary.get("rollenquelle") or "unbekannt"),
                    "analyse": str(summary.get("letzte_pruefung") or "unbekannt"),
                    "betriebssystem": self._formatiere_detailwert(summary.get("betriebssystem") or summary.get("os")),
                    "dienste": self._formatiere_detailwert(summary.get("dienste")),
                    "ports": self._formatiere_detailwert(summary.get("ports")),
                    "hinweise": self._formatiere_detailwert(hinweise_liste) or "Keine Hinweise vorhanden",
                }
            )

        return zeilen

    @staticmethod
    def _formatiere_detailwert(wert: object) -> str:
        """Formatiert Detailwerte robust für die kompakte Drilldown-Ansicht."""
        if isinstance(wert, list):
            teile = [str(eintrag).strip() for eintrag in wert if str(eintrag).strip()]
            return ", ".join(teile)
        if isinstance(wert, dict):
            teile = [f"{schluessel}: {inhalt}" for schluessel, inhalt in wert.items()]
            return ", ".join(teile)
        return str(wert).strip()

    def _lade_serversektion(self) -> None:
        """Lädt die Tabellenzeilen für die Serversektion und setzt Default-Details."""
        if not hasattr(self, "server_uebersicht"):
            return

        for item_id in self.server_uebersicht.get_children(""):
            self.server_uebersicht.delete(item_id)

        self._serveransicht_index = {}
        module = self.state_store.lade_gesamtzustand().get("modules", {})
        zeilen = self._baue_serveransicht_zeilen(module if isinstance(module, dict) else {})
        for index, zeile in enumerate(zeilen):
            item_id = f"server_{index}"
            self._serveransicht_index[item_id] = zeile
            self.server_uebersicht.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    zeile["servername"],
                    zeile["fqdn"],
                    zeile["ip"],
                    zeile["reach"],
                    zeile["rollen"],
                    zeile["rollenquelle"],
                    zeile["analyse"],
                ),
            )

        self._serversektion_toggle_text.set(f"▾ Übernommene Server ({len(zeilen)})")
        self._setze_serverdetails(None)
        if zeilen:
            erstes_item = next(iter(self._serveransicht_index))
            self.server_uebersicht.selection_set(erstes_item)
            self._setze_serverdetails(self._serveransicht_index.get(erstes_item))

    def _bei_serverauswahl(self, _event: tk.Event) -> None:
        """Aktualisiert die Detailansicht bei Serverauswahl im Treeview."""
        if not hasattr(self, "server_uebersicht"):
            return
        auswahl = self.server_uebersicht.selection()
        if not auswahl:
            self._setze_serverdetails(None)
            return
        self._setze_serverdetails(self._serveransicht_index.get(auswahl[0]))

    def _setze_serverdetails(self, serverdetails: dict[str, object] | None) -> None:
        """Setzt die Drilldown-Informationen für den aktuell gewählten Server."""
        defaults = {
            "betriebssystem": "Keine Daten verfügbar",
            "dienste": "Keine Daten verfügbar",
            "ports": "Keine Daten verfügbar",
            "hinweise": "Keine Daten verfügbar",
        }
        for schluessel, fallback in defaults.items():
            text = fallback if not serverdetails else str(serverdetails.get(schluessel) or fallback)
            self._serverdetail_vars[schluessel].set(text)

    def _baue_modul_card(
        self,
        parent: ttk.Frame,
        *,
        zeile: int,
        spalte: int,
        titel: str,
        beschreibung: str,
        command: Callable[[], None],
        status_key: str,
        button_text: str,
    ) -> None:
        """Erzeugt eine modulare Card mit wiederverwendetem Card-Baustein."""
        titel_var = tk.StringVar(value=titel)
        beschreibung_var = tk.StringVar(value=beschreibung)
        status_var = tk.StringVar(value=f"{STATUS_PREFIX} unbekannt")
        technische_details_var = tk.StringVar(value="Technische Details: Noch keine Daten vorhanden.")

        self._karten_titel[status_key] = titel_var
        self._karten_beschreibung[status_key] = beschreibung_var
        self._karten_status[status_key] = status_var
        self._karten_technische_details[status_key] = technische_details_var

        sekundaer_text = None
        sekundaer_aktion = None
        if status_key == "installation":
            sekundaer_text = "Vollinstallation (Expertenmodus)"
            sekundaer_aktion = lambda: self.installieren(expertenmodus=True)

        card_elemente = baue_card_baustein(
            parent,
            titel=titel_var,
            beschreibung=beschreibung_var,
            status=status_var,
            primaer_text=button_text,
            primaer_aktion=command,
            sekundaer_text=sekundaer_text,
            sekundaer_aktion=sekundaer_aktion,
            technische_details=technische_details_var,
        )
        card = card_elemente["card"]
        card.grid(row=zeile, column=spalte, sticky="nsew", padx=6, pady=6)

        self._karten_buttons[status_key] = card_elemente["primaer_button"]  # type: ignore[assignment]
        if status_key == "installation" and card_elemente["sekundaer_button"] is not None:
            self._karten_experten_buttons[status_key] = card_elemente["sekundaer_button"]  # type: ignore[assignment]

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
            kerninfos = modulwerte.get("letzte_kerninfos", [])
            infos = "; ".join(kerninfos) if kerninfos else "Keine Daten"

            # Für die Serveranalyse verweist die Modulübersicht auf die strukturierte Servertabelle.
            if modulname == "server_analysis":
                serverliste = modulwerte.get("server_summary", [])
                anzahl_server = len(serverliste) if isinstance(serverliste, list) else 0
                infos = f"{anzahl_server} Server in der Tabelle 'Übernommene Server'"

            berichte = "; ".join(modulwerte.get("bericht_verweise", [])) or "Keine Verweise"
            self.uebersicht.insert("", "end", values=(modulname, infos, berichte))

    def _aktualisiere_dashboard_status(self) -> None:
        """Berechnet den Status je Modul für die Dashboard-Cards."""
        module = self.state_store.lade_gesamtzustand().get("modules", {})
        status_texte = {
            "installation": "Noch nicht installiert",
            "serveranalyse": "Noch keine Analyse durchgeführt",
            "ordnerverwaltung": "Noch keine Ordnerprüfung durchgeführt",
            "dokumentation": "Noch keine Dokumentation erstellt",
        }

        # Primäre Quelle für den Installationsstatus bleibt die technische Installationsprüfung
        # (Marker + Integrität). Der GUI-State ergänzt diese Information für Bericht/Version.
        installationspruefung = pruefe_installationszustand()
        update_kontext = ermittle_update_kontext(installationspruefung)
        installer_modul = module.get("installer", {}) if isinstance(module.get("installer"), dict) else {}
        if installationspruefung.installiert:
            version = installer_modul.get("version") or installationspruefung.erkannte_version or ""
            letzte_aktion = installer_modul.get("letzte_aktion")
            modus_text = "Wartung" if letzte_aktion == "maintenance" else "Installation"
            if update_kontext.update_erforderlich:
                status_texte["installation"] = (
                    f"Update verfügbar ({update_kontext.installierte_version or version or 'unbekannt'} → {update_kontext.ziel_version})"
                )
            else:
                status_texte["installation"] = (
                    f"Installiert ({version}) · Letzte Aktion: {modus_text}" if version else f"Installiert · Letzte Aktion: {modus_text}"
                )
        elif installer_modul.get("installiert"):
            status_texte["installation"] = "Teilweise installiert (Prüfung erforderlich)"

        serveranalyse_modul = module.get("server_analysis", {})
        if serveranalyse_modul.get("server_summary"):
            anzahl_server = len(serveranalyse_modul.get("server_summary", []))
            status_texte["serveranalyse"] = f"Analyseergebnisse vorhanden ({anzahl_server} Server)"
        elif serveranalyse_modul.get("letzte_kerninfos"):
            status_texte["serveranalyse"] = "Analyse vorbereitet (ohne Ergebnis-Snapshot)"
        if module.get("folder_manager", {}).get("letzte_kerninfos"):
            status_texte["ordnerverwaltung"] = "Ordnerprüfung abgeschlossen"
        if module.get("doc_generator", {}).get("letzte_kerninfos"):
            status_texte["dokumentation"] = "Dokumentation vorhanden"

        technische_details = {
            "installation": "Marker-/Integritätsprüfung und optionaler Update-Kontext aus Installerzustand.",
            "serveranalyse": "Snapshot aus server_summary inkl. Rollenquelle und Erreichbarkeit.",
            "ordnerverwaltung": "Laufhistorie und letztes Protokoll aus Modulzustand folder_manager.",
            "dokumentation": "Berichtverweise und Kerninfos aus dem Dokumentationsmodul.",
        }

        karten_technische_details = getattr(self, "_karten_technische_details", {})
        for key, var in self._karten_status.items():
            var.set(f"{STATUS_PREFIX} {status_texte.get(key, 'unbekannt')}")
            if key in karten_technische_details:
                karten_technische_details[key].set(
                    f"Technische Details: {technische_details.get(key, 'Keine Zusatzinformationen verfügbar.')}"
                )

        self._aktualisiere_installationskarte(installationspruefung.installiert, update_kontext.update_erforderlich)

    def _aktualisiere_installationskarte(self, installiert: bool, update_erforderlich: bool) -> None:
        """Aktualisiert den Primärbutton der Installationskarte abhängig vom Zustand.

        Bei bestehender Installation wird die Aktion klar als Prüf-/Aktualisierungspfad
        gekennzeichnet, damit keine unbeabsichtigte Vollinstallation gestartet wird.
        """
        karten_buttons = getattr(self, "_karten_buttons", {})
        karten_titel = getattr(self, "_karten_titel", {})
        karten_beschreibung = getattr(self, "_karten_beschreibung", {})
        karten_experten = getattr(self, "_karten_experten_buttons", {})
        installations_button = karten_buttons.get("installation")
        if installations_button is None:
            return

        titel_var = karten_titel.get("installation")
        beschreibung_var = karten_beschreibung.get("installation")

        if installiert:
            if update_erforderlich:
                if titel_var is not None:
                    titel_var.set("Update & Wartung")
                if beschreibung_var is not None:
                    beschreibung_var.set(
                        "Prüft Versionen, führt Migrationsschritte aus und schützt persistente Daten vor dem Update."
                    )
            else:
                if titel_var is not None:
                    titel_var.set("Wartung")
                if beschreibung_var is not None:
                    beschreibung_var.set(
                        "Installationszustand ist aktuell. Startet Integritätsprüfung und optionale Wartungsschritte."
                    )
            installations_button.configure(text="Update / Wartung prüfen")
            if karten_experten.get("installation") is not None:
                karten_experten["installation"].configure(state="normal")
        else:
            if titel_var is not None:
                titel_var.set("Installation")
            if beschreibung_var is not None:
                beschreibung_var.set(
                    "Installiert alle Kernkomponenten. Danach stehen Analyse-, Ordner- und Doku-Module bereit."
                )
            installations_button.configure(text="Installation starten")
            if karten_experten.get("installation") is not None:
                karten_experten["installation"].configure(state="disabled")

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
            self._lade_serversektion()

    def installieren(self, *, bestaetigung_erforderlich: bool = True, expertenmodus: bool = False) -> None:
        """Öffnet den Installationsassistenten mit Guard gegen unbeabsichtigte Vollinstallationen."""
        installationspruefung = pruefe_installationszustand()
        update_kontext = ermittle_update_kontext(installationspruefung)
        modus = update_kontext.modus

        if installationspruefung.installiert and not expertenmodus:
            modus = "maintenance"
            if bestaetigung_erforderlich and not self.shell.bestaetige_aktion(
                "Update / Wartung prüfen",
                (
                    "Das System ist bereits installiert. Es wird der Wartungsmodus geöffnet.\n"
                    f"Versionskontext: {update_kontext.installierte_version or 'unbekannt'} → {update_kontext.ziel_version}."
                ),
            ):
                self.shell.setze_status("Wartung abgebrochen")
                return
            self.shell.setze_status("Wartungsassistent wird geöffnet")
        else:
            if bestaetigung_erforderlich and not self.shell.bestaetige_aktion(
                "Installation bestätigen",
                "Der grafische Installationsassistent wird geöffnet.",
            ):
                self.shell.setze_status("Installation abgebrochen")
                return

            if installationspruefung.installiert and expertenmodus:
                self.shell.logge_meldung("Vollinstallation im Expertenmodus angefordert.")
            self.shell.setze_status("Installationsassistent wird geöffnet")

        lauf_id = self._starte_neuen_lauf()
        status_label = "Wartungsassistent geöffnet" if modus == "maintenance" else "Installationsassistent geöffnet"
        self.shell.setze_status(status_label)
        self.shell.logge_meldung(f"[{lauf_id}] Öffne grafischen Assistenten im Modus: {modus}")

        InstallerWizardGUI(
            self.master,
            mode=modus,
            on_finished=lambda erfolgreich: self._nach_installation(erfolgreich, lauf_id, modus),
        )

    def _nach_installation(self, erfolgreich: bool, lauf_id: str, modus: str) -> None:
        """Synchronisiert Dashboard und Status nach Abschluss des Installer-Dialogs."""
        vorgang = "Wartung" if modus == "maintenance" else "Installation"
        if erfolgreich:
            self.shell.zeige_erfolg(
                "Erfolg",
                f"{vorgang} abgeschlossen.\nLauf-ID: {lauf_id}",
                "Prüfen Sie die Übersicht und speichern Sie bei Bedarf den Zustand.",
            )
            self.shell.setze_status(f"{vorgang} abgeschlossen")
        else:
            self.shell.zeige_warnung(
                f"{vorgang} unvollständig",
                f"Die {vorgang.lower()} wurde mit Fehlern beendet.\nLauf-ID: {lauf_id}",
                "Prüfen Sie die Meldungen im Installer-Fenster und wiederholen Sie den Vorgang.",
            )
            self.shell.setze_status(f"{vorgang} mit Warnungen beendet")

        self._lade_uebersichtszeilen()
        self._aktualisiere_dashboard_status()
        self._lade_serversektion()

    def _installation_erforderlich_dialog(self, modulname: str) -> bool:
        """Blockiert Modulstarts ohne valide Installation und nutzt genau einen Bestätigungsdialog."""
        pruefung = pruefe_installationszustand()
        if pruefung.installiert:
            return True

        gruende = "\n- " + "\n- ".join(pruefung.gruende) if pruefung.gruende else ""
        if messagebox.askyesno(
            "Installation starten",
            f"{modulname} ist noch nicht freigeschaltet.{gruende}\n\n"
            "Jetzt den Installationsassistenten öffnen?",
            parent=self.master,
        ):
            self.installieren(bestaetigung_erforderlich=False)
        else:
            self.shell.setze_status(f"{modulname}: Installation vor Nutzung erforderlich")
        return False

    def serveranalyse(self) -> None:
        if not self._installation_erforderlich_dialog("Serveranalyse"):
            return
        self._execute_command("Serveranalyse", [sys.executable, "src/server_analysis_gui.py"])

    def ordner_verwalten(self) -> None:
        if not self._installation_erforderlich_dialog("Ordnerverwaltung"):
            return

        if not self.shell.bestaetige_aktion(
            "Ordnerverwaltung bestätigen",
            "Der grafische Ordner-/Freigabeassistent wird geöffnet.",
        ):
            self.shell.setze_status("Ordnerverwaltung abgebrochen")
            return

        lauf_id = self._starte_neuen_lauf()
        self.shell.setze_status("Ordner-/Freigabeassistent geöffnet")
        self.shell.logge_meldung(f"[{lauf_id}] Öffne grafischen Ordner-/Freigabeassistenten")
        FolderWizardGUI(self.master)

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
        self._lade_serversektion()
        self.shell.setze_status("Launcher-Zustand gespeichert")
        self.shell.logge_meldung(f"Zustand gespeichert unter: {self.state_store.dateipfad}")

    def zurueck(self) -> None:
        """Navigationsaktion: im Launcher bedeutet Zurück eine Übersichts-Aktualisierung."""
        self._lade_uebersichtszeilen()
        self._aktualisiere_dashboard_status()
        self._lade_serversektion()
        self.shell.setze_status("Übersicht aktualisiert")


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    SystemManagerGUI(root)
    root.mainloop()
