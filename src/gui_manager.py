"""Tkinter-basierte Startoberfläche mit Dashboard und geführtem Onboarding."""

from __future__ import annotations

from datetime import datetime
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
from systemmanager_sagehelper.models import AnalyseErgebnis
from systemmanager_sagehelper.targeting import normalisiere_servernamen
from systemmanager_sagehelper.ui_theme import LAYOUT
from server_analysis_gui import MehrserverAnalyseGUI, ServerTabellenZeile, _baue_serverziele

logger = konfiguriere_logger(__name__, dateiname="gui_manager.log")

_ONBOARDING_VERSION = "1.0.0"


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

    def starte_wizard(self) -> None:
        """Öffnet den geführten Onboarding-Wizard als modalen Dialog."""
        if self._window and self._window.winfo_exists():
            self._window.lift()
            return

        self._window = tk.Toplevel(self.gui.master)
        self._window.title("Erststart-Wizard")
        self._window.geometry("760x460")
        self._window.transient(self.gui.master)
        self._window.grab_set()
        self._window.protocol("WM_DELETE_WINDOW", self._abbrechen)

        self._status_var = tk.StringVar(value="Bereit: Schritt 1 starten (Netzwerk-Discovery).")
        self._analyse_pfad_var = tk.StringVar(value="docs/serverbericht.md")

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
                "Folgen Sie den 4 Schritten: Discovery → Rollen prüfen → Analyse → Daten speichern.\n"
                "Der Wizard bleibt getrennt vom normalen Dashboard-Betrieb."
            ),
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        ttk.Label(rahmen, text="Discovery-Range (CIDR oder Basis wie 192.168.178):").pack(anchor="w")
        self._discovery_entry = ttk.Entry(rahmen, width=40)
        self._discovery_entry.insert(0, "192.168.178")
        self._discovery_entry.pack(anchor="w", pady=(2, 10))

        start_ende_rahmen = ttk.Frame(rahmen)
        start_ende_rahmen.pack(anchor="w", pady=(0, 10))
        ttk.Label(start_ende_rahmen, text="Start:").pack(side="left")
        self._discovery_start_entry = ttk.Entry(start_ende_rahmen, width=6)
        self._discovery_start_entry.insert(0, "1")
        self._discovery_start_entry.pack(side="left", padx=(4, 12))
        ttk.Label(start_ende_rahmen, text="Ende:").pack(side="left")
        self._discovery_ende_entry = ttk.Entry(start_ende_rahmen, width=6)
        self._discovery_ende_entry.insert(0, "30")
        self._discovery_ende_entry.pack(side="left", padx=(4, 0))

        ttk.Label(rahmen, text="Analyse-Reportpfad:").pack(anchor="w")
        ttk.Entry(rahmen, textvariable=self._analyse_pfad_var, width=55).pack(anchor="w", pady=(2, 10))

        schritte = ttk.Frame(rahmen)
        schritte.pack(fill="x", pady=(6, 10))
        schritte.columnconfigure((0, 1), weight=1)

        ttk.Button(schritte, text="1) Discovery ausführen", command=self.schritt_discovery).grid(
            row=0, column=0, sticky="ew", padx=(0, 6), pady=4
        )
        ttk.Button(schritte, text="2) Rollen prüfen/anpassen", command=self.schritt_rollen_pruefen).grid(
            row=0, column=1, sticky="ew", padx=(6, 0), pady=4
        )
        ttk.Button(schritte, text="3) Analyse ausführen", command=self.schritt_analyse).grid(
            row=1, column=0, sticky="ew", padx=(0, 6), pady=4
        )
        ttk.Button(schritte, text="4) Daten speichern & abschließen", command=self.schritt_speichern_und_abschliessen).grid(
            row=1, column=1, sticky="ew", padx=(6, 0), pady=4
        )

        ttk.Label(rahmen, textvariable=self._status_var, wraplength=700, justify="left").pack(anchor="w", pady=(8, 0))

    def schritt_discovery(self) -> None:
        """Schritt 1: Führt die Discovery durch und befüllt das Tabellenmodell."""
        discovery_eingabe = self._discovery_entry.get().strip() if self._window else ""
        start_eingabe = self._discovery_start_entry.get().strip() if self._window else ""
        ende_eingabe = self._discovery_ende_entry.get().strip() if self._window else ""

        try:
            discovery_basis, start, ende = self._parse_discovery_eingabe(discovery_eingabe, start_eingabe, ende_eingabe)
        except ValueError as exc:
            self._setze_status(str(exc))
            return

        self._setze_status("Discovery läuft …")
        try:
            ergebnisse = entdecke_server_ergebnisse(
                basis=discovery_basis,
                start=start,
                ende=ende,
                konfiguration=DiscoveryKonfiguration(),
            )
        except Exception as exc:  # noqa: BLE001 - Wizard soll robust weiterlaufen.
            logger.exception("Discovery im Onboarding fehlgeschlagen")
            self._setze_status(f"Discovery fehlgeschlagen: {exc}")
            return

        self.server_zeilen = []
        for treffer in ergebnisse:
            rollen = ["APP"]
            if "1433" in treffer.erkannte_dienste:
                rollen = ["SQL"]
            elif "3389" in treffer.erkannte_dienste:
                rollen = ["CTX"]

            self.server_zeilen.append(
                ServerTabellenZeile(
                    servername=treffer.hostname,
                    sql="SQL" in rollen,
                    app="APP" in rollen,
                    ctx="CTX" in rollen,
                    quelle="discovery",
                    status="entdeckt",
                    auto_rolle=rollen[0],
                )
            )

        self.gui.modulzustand["letzte_discovery_range"] = f"{discovery_basis}.{start}-{ende}"
        self._setze_status(f"Discovery abgeschlossen: {len(self.server_zeilen)} Server übernommen.")

    @staticmethod
    def _parse_discovery_eingabe(discovery_eingabe: str, start_eingabe: str, ende_eingabe: str) -> tuple[str, int, int]:
        """Parst Discovery-Eingaben robust für Basis + Start/Ende inklusive Kurzformat.

        Unterstützte Eingaben:
        * Basis + getrennte Start/Ende-Felder (z. B. 192.168.0 + 1/30)
        * Kurzformat in einem Feld (z. B. 192.168.0.1-30)
        """

        beispiel = "192.168.0 + Start=1 und Ende=30 oder 192.168.0.1-30"
        if not discovery_eingabe:
            raise ValueError(f"Ungültige Discovery-Eingabe. Beispiele: {beispiel}")

        kurzformat = re.fullmatch(r"(?P<basis>(?:\d{1,3}\.){2}\d{1,3})\.(?P<start>\d{1,3})-(?P<ende>\d{1,3})", discovery_eingabe)
        if kurzformat:
            basis = kurzformat.group("basis")
            start = int(kurzformat.group("start"))
            ende = int(kurzformat.group("ende"))
        else:
            basis = discovery_eingabe
            if not re.fullmatch(r"(?:\d{1,3}\.){2}\d{1,3}", basis):
                raise ValueError(f"Ungültiges Discovery-Format. Beispiele: {beispiel}")
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

        return basis, start, ende

    def schritt_rollen_pruefen(self) -> None:
        """Schritt 2: Ermöglicht eine einfache Rollenanpassung pro gefundenem Server."""
        if not self.server_zeilen:
            self._setze_status("Keine Discovery-Daten vorhanden. Bitte zuerst Schritt 1 ausführen.")
            return

        dialog = tk.Toplevel(self._window)
        dialog.title("Rollenprüfung")
        dialog.geometry("700x420")
        dialog.transient(self._window)
        dialog.grab_set()

        tree = ttk.Treeview(dialog, columns=("server", "rolle", "quelle"), show="headings", height=14)
        tree.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        tree.heading("server", text="Server")
        tree.heading("rolle", text="Rolle")
        tree.heading("quelle", text="Quelle")
        tree.column("server", width=280)
        tree.column("rolle", width=120, anchor="center")
        tree.column("quelle", width=180)

        for index, zeile in enumerate(self.server_zeilen):
            rolle = "SQL" if zeile.sql else "CTX" if zeile.ctx else "APP"
            tree.insert("", "end", iid=str(index), values=(zeile.servername, rolle, zeile.quelle))

        def rolle_setzen(rolle: str) -> None:
            for item_id in tree.selection():
                zeile = self.server_zeilen[int(item_id)]
                vorher = "SQL" if zeile.sql else "CTX" if zeile.ctx else "APP"
                zeile.sql = rolle == "SQL"
                zeile.app = rolle == "APP"
                zeile.ctx = rolle == "CTX"
                zeile.manuell_ueberschrieben = vorher != rolle
                zeile.status = "rolle geprüft"
                tree.set(item_id, "rolle", rolle)
                if zeile.manuell_ueberschrieben:
                    tree.set(item_id, "quelle", "onboarding-manuell")

        button_rahmen = ttk.Frame(dialog)
        button_rahmen.pack(fill="x", padx=10, pady=(0, 10))
        for rolle in ("SQL", "APP", "CTX"):
            ttk.Button(button_rahmen, text=f"Als {rolle} markieren", command=lambda r=rolle: rolle_setzen(r)).pack(
                side="left", padx=4
            )
        ttk.Button(button_rahmen, text="Fertig", command=dialog.destroy).pack(side="right", padx=4)

        self._setze_status("Rollenprüfung geöffnet: Auswahl prüfen und ggf. anpassen.")

    def schritt_analyse(self) -> None:
        """Schritt 3: Startet die Analyse auf Basis der bestätigten Rollen."""
        if not self.server_zeilen:
            self._setze_status("Keine Server vorhanden. Discovery und Rollenprüfung zuerst ausführen.")
            return

        ziele = _baue_serverziele(self.server_zeilen)
        if not ziele:
            self._setze_status("Es konnten keine gültigen Analyseziele aus dem Tabellenmodell erzeugt werden.")
            return

        self._setze_status("Analyse läuft …")
        try:
            self.analyse_ergebnisse = analysiere_mehrere_server(ziele)
        except Exception as exc:  # noqa: BLE001 - Wizard zeigt Fehler im UI an.
            logger.exception("Analyse im Onboarding fehlgeschlagen")
            self._setze_status(f"Analyse fehlgeschlagen: {exc}")
            return

        status_index = {normalisiere_servernamen(e.server): "analysiert" for e in self.analyse_ergebnisse}
        for zeile in self.server_zeilen:
            zeile.status = status_index.get(normalisiere_servernamen(zeile.servername), "nicht analysiert")

        self._setze_status(f"Analyse abgeschlossen: {len(self.analyse_ergebnisse)} Server analysiert.")

    def schritt_speichern_und_abschliessen(self) -> None:
        """Schritt 4: Persistiert Moduldaten + Onboarding-Status atomar im Gesamtzustand."""
        if not self.server_zeilen:
            self._setze_status("Es gibt keine Daten zum Speichern. Bitte vorher Schritt 1 ausführen.")
            return

        # Persistenzlogik der Serveranalyse-GUI wiederverwenden, um Datenmodell konsistent zu halten.
        self._speichere_serveranalyse_zustand_ueber_gui_methode()

        onboarding_status = self.state_store.lade_onboarding_status()
        now_iso = datetime.now().isoformat(timespec="seconds")
        onboarding_status.update(
            {
                "onboarding_abgeschlossen": True,
                "onboarding_version": _ONBOARDING_VERSION,
                "erststart_zeitpunkt": onboarding_status.get("erststart_zeitpunkt") or now_iso,
                "letzter_abschluss_zeitpunkt": now_iso,
            }
        )

        gesamtzustand = self.state_store.lade_gesamtzustand()
        gesamtzustand["onboarding"] = onboarding_status
        self.state_store.speichere_gesamtzustand(gesamtzustand)

        self.gui.modulzustand = self.state_store.lade_modulzustand("gui_manager")
        self.gui._lade_uebersichtszeilen()
        self.gui._aktualisiere_dashboard_status()

        self._setze_status("Onboarding abgeschlossen und vollständig gespeichert.")
        messagebox.showinfo(
            "Onboarding abgeschlossen",
            "Der Erststart wurde erfolgreich abgeschlossen. Das Dashboard kann jetzt regulär genutzt werden.",
            parent=self._window,
        )
        if self._window:
            self._window.destroy()

    def _speichere_serveranalyse_zustand_ueber_gui_methode(self) -> None:
        """Nutzt `MehrserverAnalyseGUI.speichern()`, ohne die gesamte GUI zu öffnen.

        Damit bleibt die bestehende Persistenzstruktur zentral an einer Stelle,
        und der Onboarding-Controller muss diese Logik nicht duplizieren.
        """

        adapter = object.__new__(MehrserverAnalyseGUI)
        adapter.state_store = self.state_store
        adapter.modulzustand = self.state_store.lade_modulzustand("server_analysis")
        adapter._zeilen_nach_id = {f"row-{index}": zeile for index, zeile in enumerate(self.server_zeilen, start=1)}
        adapter._letzte_ergebnisse = self.analyse_ergebnisse
        adapter._letzte_discovery_range = tk.StringVar(value=self.gui.modulzustand.get("letzte_discovery_range", ""))
        adapter._ausgabe_pfad = tk.StringVar(value=(self._analyse_pfad_var.get().strip() if self._analyse_pfad_var else "docs/serverbericht.md"))
        adapter._letzter_export_pfad = adapter.modulzustand.get("letzter_exportpfad", "")
        adapter._letzter_exportzeitpunkt = adapter.modulzustand.get("letzter_exportzeitpunkt", "")
        adapter._letzte_export_lauf_id = adapter.modulzustand.get("letzte_export_lauf_id", "")
        adapter.shell = type(
            "OnboardingShell",
            (),
            {
                "setze_status": lambda _self, _status: None,
                "logge_meldung": lambda _self, _meldung: None,
            },
        )()

        MehrserverAnalyseGUI.speichern(adapter)

        # Synchronisiere die wichtigsten Übersichtsdaten zusätzlich mit dem Launcher-Modul.
        self.gui.modulzustand.setdefault("letzte_kerninfos", [])
        self.gui.modulzustand["letzte_kerninfos"] = [
            f"Onboarding abgeschlossen: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Server in Ersterfassung: {len(self.server_zeilen)}",
        ]
        self.gui.modulzustand.setdefault("bericht_verweise", [])
        analyse_report = adapter._ausgabe_pfad.get().strip() or "docs/serverbericht.md"
        self.gui.modulzustand["bericht_verweise"] = [analyse_report]
        self.state_store.speichere_modulzustand("gui_manager", self.gui.modulzustand)

    def _abbrechen(self) -> None:
        """Schließt den Wizard ohne Abschlussflag und markiert den Zustand klar."""
        self._setze_status("Onboarding abgebrochen: Dashboard bleibt im eingeschränkten Erststartmodus.")
        if self._window:
            self._window.destroy()

    def _setze_status(self, text: str) -> None:
        """Aktualisiert die Wizard-Statuszeile zentral und robust."""
        if self._status_var is not None:
            self._status_var.set(text)
        logger.info("[Onboarding] %s", text)


class SystemManagerGUI:
    """Kapselt Aufbau und Verhalten der Launcher-Oberfläche."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.geometry("1080x820")

        self.state_store = GUIStateStore()
        self.modulzustand = self.state_store.lade_modulzustand("gui_manager")

        self.shell = GuiShell(
            master,
            titel="SystemManager-SageHelper",
            untertitel="Dashboard für Analyse, Ordnermanagement und Dokumentation",
            on_save=self.speichern,
            on_back=self.zurueck,
            on_exit=self.master.quit,
        )

        self._karten_status: dict[str, tk.StringVar] = {}
        self._karten_buttons: dict[str, ttk.Button] = {}
        self._baue_dashboard()
        self._onboarding_controller = OnboardingController(self)
        self._pruefe_onboarding_guard()

    def _pruefe_onboarding_guard(self) -> None:
        """Startet beim Erststart automatisch den geführten Wizard."""
        onboarding_status = self.state_store.lade_onboarding_status()
        if not onboarding_status.get("erststart_zeitpunkt"):
            onboarding_status["erststart_zeitpunkt"] = datetime.now().isoformat(timespec="seconds")
            onboarding_status["onboarding_version"] = onboarding_status.get("onboarding_version") or _ONBOARDING_VERSION
            self.state_store.speichere_onboarding_status(onboarding_status)

        if not onboarding_status.get("onboarding_abgeschlossen", False):
            self.shell.setze_status("Erststart erkannt: Onboarding-Wizard wird geöffnet")
            self.master.after(150, self._onboarding_controller.starte_wizard)

    def _baue_dashboard(self) -> None:
        """Erzeugt die Startseite mit klaren Modul-Cards inklusive Statusanzeige."""
        dashboard = ttk.LabelFrame(self.shell.content_frame, text="Dashboard", style="Section.TLabelframe")
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

        cards = ttk.Frame(dashboard)
        cards.grid(row=2, column=0, sticky="ew", padx=LAYOUT.padding_inline, pady=(0, 12))
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
        """Erzeugt eine modulare Card mit Statusindikator und Primäraktion."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=LAYOUT.padding_block)
        card.grid(row=zeile, column=spalte, sticky="nsew", padx=6, pady=6)

        ttk.Label(card, text=titel, style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(card, text=beschreibung, style="Card.TLabel", wraplength=LAYOUT.card_breite).pack(
            anchor="w", pady=(6, 10)
        )

        status_var = tk.StringVar(value="Status: unbekannt")
        self._karten_status[status_key] = status_var
        ttk.Label(card, textvariable=status_var, style="Card.TLabel").pack(anchor="w", pady=(0, 10))

        # Der Button wird je nach Installationszustand dynamisch umbenannt bzw. deaktiviert.
        primar_button = ttk.Button(
            card,
            text=button_text,
            style="Primary.TButton",
            width=LAYOUT.button_breite,
            command=command,
        )
        primar_button.pack(anchor="w")
        self._karten_buttons[status_key] = primar_button

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
            infos = "; ".join(modulwerte.get("letzte_kerninfos", [])) or "Keine Daten"
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
        installer_modul = module.get("installer", {}) if isinstance(module.get("installer"), dict) else {}
        if installationspruefung.installiert:
            version = installer_modul.get("version") or installationspruefung.erkannte_version or ""
            status_texte["installation"] = (
                f"Installiert ({version})" if version else "Installiert"
            )
        elif installer_modul.get("installiert"):
            status_texte["installation"] = "Teilweise installiert (Prüfung erforderlich)"

        if module.get("server_analysis", {}).get("letzte_kerninfos"):
            status_texte["serveranalyse"] = "Analyseergebnisse vorhanden"
        if module.get("folder_manager", {}).get("letzte_kerninfos"):
            status_texte["ordnerverwaltung"] = "Ordnerprüfung abgeschlossen"
        if module.get("doc_generator", {}).get("letzte_kerninfos"):
            status_texte["dokumentation"] = "Dokumentation vorhanden"

        for key, var in self._karten_status.items():
            var.set(f"Status: {status_texte.get(key, 'unbekannt')}")

        self._aktualisiere_installationskarte(installationspruefung.installiert)

    def _aktualisiere_installationskarte(self, installiert: bool) -> None:
        """Aktualisiert den Primärbutton der Installationskarte abhängig vom Zustand.

        Bei bestehender Installation wird die Aktion klar als Prüf-/Aktualisierungspfad
        gekennzeichnet, damit keine unbeabsichtigte Vollinstallation gestartet wird.
        """
        installations_button = self._karten_buttons.get("installation")
        if installations_button is None:
            return

        if installiert:
            installations_button.configure(text="Installation prüfen/aktualisieren")
        else:
            installations_button.configure(text="Installation starten")

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

    def installieren(self, *, bestaetigung_erforderlich: bool = True, expertenmodus: bool = False) -> None:
        """Öffnet den Installationsassistenten mit Guard gegen unbeabsichtigte Vollinstallationen."""
        installationspruefung = pruefe_installationszustand()

        if installationspruefung.installiert and not expertenmodus:
            if bestaetigung_erforderlich and not self.shell.bestaetige_aktion(
                "Installation prüfen oder aktualisieren",
                "Das System ist bereits installiert. Es wird keine Vollinstallation gestartet.",
            ):
                self.shell.setze_status("Prüfung/Aktualisierung abgebrochen")
                return
            self.shell.setze_status("Installationsprüfung/Aktualisierung wird geöffnet")
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
        self.shell.setze_status("Installationsassistent geöffnet")
        self.shell.logge_meldung(f"[{lauf_id}] Öffne grafischen Installationsassistenten")

        InstallerWizardGUI(
            self.master,
            on_finished=lambda erfolgreich: self._nach_installation(erfolgreich, lauf_id),
        )

    def _nach_installation(self, erfolgreich: bool, lauf_id: str) -> None:
        """Synchronisiert Dashboard und Status nach Abschluss des Installer-Dialogs."""
        if erfolgreich:
            self.shell.zeige_erfolg(
                "Erfolg",
                f"Installation abgeschlossen.\nLauf-ID: {lauf_id}",
                "Prüfen Sie die Übersicht und speichern Sie bei Bedarf den Zustand.",
            )
            self.shell.setze_status("Installation abgeschlossen")
        else:
            self.shell.zeige_warnung(
                "Installation unvollständig",
                f"Die Installation wurde mit Fehlern beendet.\nLauf-ID: {lauf_id}",
                "Prüfen Sie die Meldungen im Installer-Fenster und wiederholen Sie den Vorgang.",
            )
            self.shell.setze_status("Installation mit Warnungen beendet")

        self._lade_uebersichtszeilen()
        self._aktualisiere_dashboard_status()

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
        self.shell.setze_status("Launcher-Zustand gespeichert")
        self.shell.logge_meldung(f"Zustand gespeichert unter: {self.state_store.dateipfad}")

    def zurueck(self) -> None:
        """Navigationsaktion: im Launcher bedeutet Zurück eine Übersichts-Aktualisierung."""
        self._lade_uebersichtszeilen()
        self._aktualisiere_dashboard_status()
        self.shell.setze_status("Übersicht aktualisiert")


if __name__ == "__main__":
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    SystemManagerGUI(root)
    root.mainloop()
