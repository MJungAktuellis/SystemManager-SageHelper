"""Mehrserver-GUI für die Serveranalyse mit gemeinsamem Shell-Konzept."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk

from systemmanager_sagehelper.analyzer import (
    analysiere_mehrere_server,
    DiscoveryKonfiguration,
    entdecke_server_ergebnisse,
)
from systemmanager_sagehelper.gui_shell import GuiShell
from systemmanager_sagehelper.installation_state import pruefe_installationszustand, verarbeite_installations_guard
from systemmanager_sagehelper.gui_state import GUIStateStore
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from systemmanager_sagehelper.models import AnalyseErgebnis, DiscoveryErgebnis, ServerZiel
from systemmanager_sagehelper.config import STANDARD_PORTS
from systemmanager_sagehelper.report import render_markdown
from systemmanager_sagehelper.targeting import normalisiere_servernamen, rollen_aus_bool_flags


@dataclass
class ServerTabellenZeile:
    """Zeilenmodell für die GUI-Tabelle mit Deklaration eines Zielservers."""

    servername: str
    sql: bool = False
    app: bool = True
    ctx: bool = False
    quelle: str = "manuell"
    status: str = "neu"
    auto_rolle: str | None = None
    manuell_ueberschrieben: bool = False

    def rollen(self) -> list[str]:
        """Leitet die Rollenliste aus den gesetzten Checkboxen ab."""
        return rollen_aus_bool_flags(sql=self.sql, app=self.app, ctx=self.ctx)


_SPALTE_SERVERNAME = "servername"
_SPALTE_SQL = "sql"
_SPALTE_APP = "app"
_SPALTE_CTX = "ctx"
_SPALTE_QUELLE = "quelle"
_SPALTE_STATUS = "status"
_SPALTEN = (_SPALTE_SERVERNAME, _SPALTE_SQL, _SPALTE_APP, _SPALTE_CTX, _SPALTE_QUELLE, _SPALTE_STATUS)
_ROLLEN_SPALTEN = {_SPALTE_SQL: "sql", _SPALTE_APP: "app", _SPALTE_CTX: "ctx"}
_CHECK_AN = "☑"
_CHECK_AUS = "☐"
_KRITISCHE_PORTS = {port.port for port in STANDARD_PORTS}


logger = konfiguriere_logger(__name__, dateiname="server_analysis_gui.log")

_IPV4_BASIS_REGEX = re.compile(r"^(?:25[0-5]|2[0-4]\d|1?\d?\d)\.(?:25[0-5]|2[0-4]\d|1?\d?\d)\.(?:25[0-5]|2[0-4]\d|1?\d?\d)$")


def _checkbox_wert(aktiv: bool) -> str:
    """Formatiert boolesche Rollenwerte als visuelles Checkbox-Symbol."""
    return _CHECK_AN if aktiv else _CHECK_AUS


def _baue_serverziele(zeilen: list[ServerTabellenZeile]) -> list[ServerZiel]:
    """Erzeugt Analyse-DTOs aus dem Zeilenmodell der GUI-Tabelle."""
    ziele: list[ServerZiel] = []
    for zeile in zeilen:
        name = zeile.servername.strip()
        if not name:
            continue
        ziele.append(
            ServerZiel(
                name=name,
                rollen=zeile.rollen(),
                rollenquelle=_rollenquelle_fuer_zeile(zeile),
                auto_rollen=[zeile.auto_rolle] if zeile.auto_rolle else [],
                manuell_ueberschrieben=zeile.manuell_ueberschrieben,
            )
        )
    return ziele


def _rollenquelle_fuer_zeile(zeile: ServerTabellenZeile) -> str:
    """Ermittelt die Herkunft der finalen Rollendeklaration für einen Server."""
    if zeile.quelle.lower() == "discovery" and not zeile.manuell_ueberschrieben:
        return "automatisch erkannt"
    if zeile.manuell_ueberschrieben and zeile.auto_rolle:
        return "nachträglich geändert"
    return "manuell gesetzt"


def _deklarationszusammenfassung(ziele: list[ServerZiel], zeilen: list[ServerTabellenZeile]) -> str:
    """Erzeugt eine lesbare Zusammenfassung vor Ausführung der Analyse."""
    quelle_pro_server = {normalisiere_servernamen(zeile.servername): zeile.quelle for zeile in zeilen}
    zusammenfassung = ["So wurden die Server deklariert:"]
    for index, ziel in enumerate(ziele, start=1):
        rollen = ", ".join(ziel.rollen) if ziel.rollen else "keine Rolle gesetzt"
        quelle = quelle_pro_server.get(normalisiere_servernamen(ziel.name), "unbekannt")
        zusammenfassung.append(
            f"{index}. {ziel.name} | Rollen: {rollen} | Quelle: {quelle} | Rollenquelle: {ziel.rollenquelle or 'unbekannt'}"
        )
    return "\n".join(zusammenfassung)


def _kurzstatus(ergebnis: AnalyseErgebnis) -> str:
    """Erzeugt einen kompakten Statussatz je Server für die aufklappbare Liste."""
    offene_ports = [str(port.port) for port in ergebnis.ports if port.offen]
    rollen = ", ".join(ergebnis.rollen) if ergebnis.rollen else "nicht gesetzt/ermittelt"
    quelle = ergebnis.rollenquelle or "unbekannt"
    return f"Rollen: {rollen} | Quelle: {quelle} | Offene Ports: {', '.join(offene_ports) if offene_ports else 'keine'}"


def _baue_executive_summary(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Verdichtet Analyseergebnisse für die Management-Sicht in der GUI."""
    if not ergebnisse:
        return ["Keine Analyseergebnisse vorhanden."]

    rollenverteilung = {"SQL": 0, "APP": 0, "CTX": 0}
    offene_kritische_ports = 0
    warnungen = 0
    hinweise = 0

    for ergebnis in ergebnisse:
        for rolle in ergebnis.rollen:
            if rolle in rollenverteilung:
                rollenverteilung[rolle] += 1
        offene_kritische_ports += sum(1 for port in ergebnis.ports if port.offen and port.port in _KRITISCHE_PORTS)
        warnungen += sum(1 for port in ergebnis.ports if not port.offen)
        warnungen += len(ergebnis.hinweise)
        hinweise += len(ergebnis.hinweise)

    return [
        f"Analysierte Server: {len(ergebnisse)}",
        f"Rollenverteilung: SQL={rollenverteilung['SQL']}, APP={rollenverteilung['APP']}, CTX={rollenverteilung['CTX']}",
        f"Offene kritische Ports: {offene_kritische_ports}",
        f"Warnungen/Hinweise gesamt: {warnungen} (davon Hinweise: {hinweise})",
    ]


def _baue_report_verweistext(exportpfad: str | None, exportzeitpunkt: str | None, lauf_id: str | None) -> str:
    """Erzeugt einen klaren Verweistext für die GUI nach Report-Export."""
    if not exportpfad:
        return "Kein Analysebericht exportiert."
    zeit = exportzeitpunkt or "Zeitpunkt unbekannt"
    lauf = lauf_id or "Lauf-ID unbekannt"
    return f"Letzter Analysebericht: {exportpfad} | Export: {zeit} | Lauf-ID: {lauf}"


def _schreibe_analyse_report(ergebnisse: list[AnalyseErgebnis], ausgabe_pfad: str) -> tuple[str, str]:
    """Rendert und schreibt den Analysebericht in den gewünschten Dateipfad."""
    zielpfad = Path(ausgabe_pfad).expanduser()
    markdown = render_markdown(ergebnisse, berichtsmodus="voll")
    zielpfad.parent.mkdir(parents=True, exist_ok=True)
    zielpfad.write_text(markdown, encoding="utf-8")
    return str(zielpfad), datetime.now().isoformat(timespec="seconds")


def _drilldown_knoten(ergebnis: AnalyseErgebnis) -> dict[str, list[str]]:
    """Bereitet die Drilldown-Hierarchie für die Ergebnisansicht auf."""
    rollenpruefung = [
        (
            "SQL: "
            + ("erkannt" if ergebnis.rollen_details.sql.erkannt else "nicht erkannt")
            + f" | Instanzen: {', '.join(ergebnis.rollen_details.sql.instanzen) or 'keine'}"
        ),
        (
            "APP: "
            + ("erkannt" if ergebnis.rollen_details.app.erkannt else "nicht erkannt")
            + f" | Sage-Versionen: {', '.join(ergebnis.rollen_details.app.sage_versionen) or 'keine'}"
        ),
        (
            "CTX: "
            + ("erkannt" if ergebnis.rollen_details.ctx.erkannt else "nicht erkannt")
            + f" | Session-Indikatoren: {', '.join(ergebnis.rollen_details.ctx.session_indikatoren) or 'keine'}"
        ),
    ]
    ports = [
        f"Port {port.port} ({port.bezeichnung}): {'offen' if port.offen else 'blockiert/unerreichbar'}" for port in ergebnis.ports
    ] or ["Keine Portdaten verfügbar"]
    dienste = [f"Dienst: {dienst.name} ({dienst.status or 'unbekannt'})" for dienst in ergebnis.dienste] or ["Keine Dienste erkannt"]
    software = [f"Software: {eintrag.name} {eintrag.version or ''}".strip() for eintrag in ergebnis.software] or ["Keine Softwaredaten erkannt"]
    return {
        "Rollenprüfung": rollenpruefung,
        "Ports": ports,
        "Dienste/Software": [*dienste, *software],
    }



@dataclass
class DiscoveryTabellenTreffer:
    """Bearbeitbares GUI-Modell für Discovery-Treffer vor der Übernahme."""

    hostname: str
    ip_adresse: str
    erreichbar: bool
    dienste: str
    vertrauensgrad: float


class DiscoveryTrefferDialog:
    """Dialog zur Auswahl, Filterung und Korrektur von Discovery-Treffern."""

    def __init__(self, parent: tk.Misc, treffer: list[DiscoveryErgebnis]) -> None:
        self._treffer = [
            DiscoveryTabellenTreffer(
                hostname=item.hostname,
                ip_adresse=item.ip_adresse,
                erreichbar=item.erreichbar,
                dienste=", ".join(item.erkannte_dienste) or "-",
                vertrauensgrad=item.vertrauensgrad,
            )
            for item in treffer
        ]
        self.ausgewaehlt: list[DiscoveryTabellenTreffer] = []

        self.window = tk.Toplevel(parent)
        self.window.title("Discovery-Treffer prüfen")
        self.window.geometry("900x520")
        self.window.transient(parent)
        self.window.grab_set()

        self.filter_var = tk.StringVar(value="")
        self.filter_var.trace_add("write", lambda *_: self._render_treffer())

        kopf = ttk.Frame(self.window)
        kopf.pack(fill="x", padx=8, pady=8)
        ttk.Label(kopf, text="Filter (Hostname/IP):").pack(side="left")
        ttk.Entry(kopf, textvariable=self.filter_var, width=30).pack(side="left", padx=6)
        ttk.Button(kopf, text="Alle auswählen", command=self._waehle_alle).pack(side="left", padx=4)
        ttk.Button(kopf, text="Auswahl übernehmen", command=self._uebernehmen).pack(side="right", padx=4)

        self.tree = ttk.Treeview(
            self.window,
            columns=("hostname", "ip", "erreichbar", "dienste", "vertrauen"),
            show="headings",
            selectmode="extended",
            height=17,
        )
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.heading("hostname", text="Hostname (bearbeitbar)")
        self.tree.heading("ip", text="IP")
        self.tree.heading("erreichbar", text="Erreichbar")
        self.tree.heading("dienste", text="Dienste")
        self.tree.heading("vertrauen", text="Vertrauensgrad")
        self.tree.column("hostname", width=220)
        self.tree.column("ip", width=150)
        self.tree.column("erreichbar", width=90, anchor="center")
        self.tree.column("dienste", width=260)
        self.tree.column("vertrauen", width=100, anchor="e")
        self.tree.bind("<Double-1>", self._bearbeite_hostname)

        self._id_zu_treffer: dict[str, DiscoveryTabellenTreffer] = {}
        self._render_treffer()

    def _render_treffer(self) -> None:
        for item_id in self.tree.get_children(""):
            self.tree.delete(item_id)
        self._id_zu_treffer.clear()

        filtertext = self.filter_var.get().strip().lower()
        for treffer in self._treffer:
            if filtertext and filtertext not in treffer.hostname.lower() and filtertext not in treffer.ip_adresse.lower():
                continue
            item_id = self.tree.insert(
                "",
                "end",
                values=(
                    treffer.hostname,
                    treffer.ip_adresse,
                    "ja" if treffer.erreichbar else "nein",
                    treffer.dienste,
                    f"{treffer.vertrauensgrad:.2f}",
                ),
            )
            self._id_zu_treffer[item_id] = treffer

    def _waehle_alle(self) -> None:
        self.tree.selection_set(self.tree.get_children(""))

    def _bearbeite_hostname(self, event: tk.Event[tk.Misc]) -> None:
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id or column != "#1":
            return
        aktueller = self._id_zu_treffer[item_id]
        neuer_hostname = simpledialog.askstring(
            "Hostname korrigieren",
            "Hostname anpassen:",
            parent=self.window,
            initialvalue=aktueller.hostname,
        )
        if neuer_hostname is None:
            return
        aktueller.hostname = neuer_hostname.strip() or aktueller.hostname
        self.tree.set(item_id, "hostname", aktueller.hostname)

    def _uebernehmen(self) -> None:
        self.ausgewaehlt = [self._id_zu_treffer[item_id] for item_id in self.tree.selection() if item_id in self._id_zu_treffer]
        self.window.destroy()


def _rollen_aus_discovery_treffer(treffer: DiscoveryTabellenTreffer) -> list[str]:
    """Leitet eine konservative Rollenvorbelegung aus Discovery-Diensten ab."""
    rollen = []
    if "1433" in treffer.dienste:
        rollen.append("SQL")
    if "3389" in treffer.dienste:
        rollen.append("CTX")
    if not rollen:
        rollen.append("APP")
    return rollen
def _detailzeilen(ergebnis: AnalyseErgebnis) -> list[str]:
    """Liefert strukturierte Detailzeilen je Server für die aufklappbare Ansicht."""
    details: list[str] = [
        f"Betriebssystem: {ergebnis.betriebssystem or 'unbekannt'} ({ergebnis.os_version or 'unbekannt'})",
        f"Rollenquelle: {ergebnis.rollenquelle or 'unbekannt'}",
        (
            "SQL-Prüfung: "
            + ("erkannt" if ergebnis.rollen_details.sql.erkannt else "nicht erkannt")
            + f" | Instanzen: {', '.join(ergebnis.rollen_details.sql.instanzen) or 'keine'}"
        ),
        (
            "APP-Prüfung: "
            + ("erkannt" if ergebnis.rollen_details.app.erkannt else "nicht erkannt")
            + f" | Sage-Versionen: {', '.join(ergebnis.rollen_details.app.sage_versionen) or 'keine'}"
        ),
        (
            "CTX-Prüfung: "
            + ("erkannt" if ergebnis.rollen_details.ctx.erkannt else "nicht erkannt")
            + f" | Indikatoren: {', '.join(ergebnis.rollen_details.ctx.session_indikatoren) or 'keine'}"
        ),
    ]

    if ergebnis.hinweise:
        details.append("Hinweise:")
        details.extend(f"- {hinweis}" for hinweis in ergebnis.hinweise)
    else:
        details.append("Hinweise: keine")

    return details


class MehrserverAnalyseGUI:
    """Tkinter-Controller für Mehrserver-Erfassung, Discovery und Ergebnisdarstellung."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.geometry("1100x820")

        self.state_store = GUIStateStore()
        self.modulzustand = self.state_store.lade_modulzustand("server_analysis")

        self.shell = GuiShell(
            master,
            titel="SystemManager-SageHelper – Mehrserveranalyse",
            untertitel="Erfassung, Discovery, Rollenpflege und Analyse auf mehreren Zielservern",
            on_save=self.speichern,
            on_back=self._zurueck,
            on_exit=self.master.destroy,
        )

        self._zeilen_nach_id: dict[str, ServerTabellenZeile] = {}
        self._letzte_ergebnisse: list[AnalyseErgebnis] = []
        self._letzte_discovery_range = tk.StringVar(value=self.modulzustand.get("letzte_discovery_range", ""))
        letzte_discovery_eingabe = self.modulzustand.get("letzte_discovery_eingabe", {})
        self._discovery_basis_var = tk.StringVar(value=str(letzte_discovery_eingabe.get("basis", "")))
        self._discovery_start_var = tk.StringVar(value=str(letzte_discovery_eingabe.get("start", "")))
        self._discovery_ende_var = tk.StringVar(value=str(letzte_discovery_eingabe.get("ende", "")))
        self._discovery_validierung_hinweis_var = tk.StringVar(value="")
        self._ausgabe_pfad = tk.StringVar(
            value=self.modulzustand.get("ausgabepfade", {}).get("analyse_report", "docs/serverbericht.md")
        )
        self._letzter_export_pfad = self.modulzustand.get("letzter_exportpfad", "")
        self._letzter_exportzeitpunkt = self.modulzustand.get("letzter_exportzeitpunkt", "")
        self._letzte_export_lauf_id = self.modulzustand.get("letzte_export_lauf_id", "")
        self._report_verweis_var = tk.StringVar(
            value=_baue_report_verweistext(
                self._letzter_export_pfad,
                self._letzter_exportzeitpunkt,
                self._letzte_export_lauf_id,
            )
        )

        self._baue_formular(self.shell.content_frame)
        self._baue_tabelle(self.shell.content_frame)
        self._baue_aktionsbereich(self.shell.content_frame)
        self._baue_ergebnisbereich(self.shell.content_frame)
        self._lade_serverliste_aus_status()
        self._aktualisiere_button_zustaende()

    def _baue_formular(self, parent: ttk.Frame) -> None:
        form_frame = ttk.LabelFrame(parent, text="Serverdeklaration", style="Section.TLabelframe")
        form_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(form_frame, text="Servername:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.entry_servername = ttk.Entry(form_frame, width=30)
        self.entry_servername.grid(row=0, column=1, padx=6)
        self.entry_servername.bind("<KeyRelease>", self._aktualisiere_button_zustaende)

        self.var_sql = tk.BooleanVar(value=False)
        self.var_app = tk.BooleanVar(value=True)
        self.var_ctx = tk.BooleanVar(value=False)

        ttk.Checkbutton(form_frame, text="SQL", variable=self.var_sql).grid(row=0, column=2, padx=4)
        ttk.Checkbutton(form_frame, text="APP", variable=self.var_app).grid(row=0, column=3, padx=4)
        ttk.Checkbutton(form_frame, text="CTX", variable=self.var_ctx).grid(row=0, column=4, padx=4)

        self.btn_hinzufuegen = ttk.Button(
            form_frame,
            text="Server manuell hinzufügen",
            style="Primary.TButton",
            command=self.server_manuell_hinzufuegen,
            state="disabled",
        )
        self.btn_hinzufuegen.grid(row=0, column=5, padx=8)

        ttk.Label(form_frame, text="IPv4-Basis (z. B. 192.168.178):").grid(row=1, column=0, sticky="w", padx=8, pady=(2, 4))
        self.entry_discovery_basis = ttk.Entry(form_frame, textvariable=self._discovery_basis_var, width=24)
        self.entry_discovery_basis.grid(row=1, column=1, padx=6, sticky="w")

        ttk.Label(form_frame, text="Start-Host (0–255):").grid(row=1, column=2, sticky="w", padx=8)
        self.entry_discovery_start = ttk.Entry(form_frame, textvariable=self._discovery_start_var, width=12)
        self.entry_discovery_start.grid(row=1, column=3, padx=6, sticky="w")

        ttk.Label(form_frame, text="End-Host (0–255):").grid(row=1, column=4, sticky="w", padx=8)
        self.entry_discovery_ende = ttk.Entry(form_frame, textvariable=self._discovery_ende_var, width=12)
        self.entry_discovery_ende.grid(row=1, column=5, padx=6, sticky="w")

        for feld in (self.entry_discovery_basis, self.entry_discovery_start, self.entry_discovery_ende):
            feld.bind("<FocusIn>", self._entferne_fehler_markierung)

        ttk.Label(
            form_frame,
            text="Beispiel: IPv4-Basis 192.168.178, Start-Host 1, End-Host 30",
            foreground="#6B7280",
        ).grid(row=2, column=0, columnspan=6, sticky="w", padx=8, pady=(0, 4))
        ttk.Label(form_frame, textvariable=self._discovery_validierung_hinweis_var, foreground="#B91C1C").grid(
            row=3,
            column=0,
            columnspan=6,
            sticky="w",
            padx=8,
            pady=(0, 6),
        )

        ttk.Label(form_frame, text="Letzte Discovery-Range:").grid(row=4, column=0, sticky="w", padx=8, pady=(2, 8))
        ttk.Entry(form_frame, textvariable=self._letzte_discovery_range, width=30).grid(row=4, column=1, padx=6, sticky="w")

        ttk.Label(form_frame, text="Analyse-Ausgabepfad:").grid(row=4, column=2, sticky="w", padx=8)
        ttk.Entry(form_frame, textvariable=self._ausgabe_pfad, width=45).grid(row=4, column=3, columnspan=3, padx=6, sticky="w")

    def _baue_tabelle(self, parent: ttk.Frame) -> None:
        table_frame = ttk.LabelFrame(parent, text="Serverliste", style="Section.TLabelframe")
        table_frame.pack(fill="both", expand=True, pady=(0, 8))

        self.tree = ttk.Treeview(table_frame, columns=_SPALTEN, show="headings", height=11)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        for spalte, titel in {
            _SPALTE_SERVERNAME: "Servername",
            _SPALTE_SQL: "SQL",
            _SPALTE_APP: "APP",
            _SPALTE_CTX: "CTX",
            _SPALTE_QUELLE: "Quelle",
            _SPALTE_STATUS: "Status",
        }.items():
            self.tree.heading(spalte, text=titel)

        self.tree.column(_SPALTE_SERVERNAME, width=220)
        self.tree.column(_SPALTE_SQL, width=70, anchor="center")
        self.tree.column(_SPALTE_APP, width=70, anchor="center")
        self.tree.column(_SPALTE_CTX, width=70, anchor="center")
        self.tree.column(_SPALTE_QUELLE, width=130)
        self.tree.column(_SPALTE_STATUS, width=180)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y", pady=8, padx=8)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Button-1>", self._toggle_rolle_per_klick)
        self.tree.bind("<<TreeviewSelect>>", self._aktualisiere_button_zustaende)

    def _baue_aktionsbereich(self, parent: ttk.Frame) -> None:
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill="x", pady=(0, 8))

        self.btn_discovery = ttk.Button(
            action_frame, text="Discovery", style="Secondary.TButton", command=self.discovery_starten
        )
        self.btn_discovery.pack(side="left", padx=4)
        self.btn_loeschen = ttk.Button(
            action_frame,
            text="Ausgewählten Eintrag löschen",
            style="Secondary.TButton",
            command=self.eintrag_loeschen,
            state="disabled",
        )
        self.btn_loeschen.pack(side="left", padx=4)
        self.btn_analyse = ttk.Button(
            action_frame, text="Analyse starten", style="Primary.TButton", command=self.analyse_starten, state="disabled"
        )
        self.btn_analyse.pack(side="right", padx=4)

    def _baue_ergebnisbereich(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Analyseergebnis je Server (Drilldown)", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)

        summary_frame = ttk.LabelFrame(frame, text="Executive Summary", style="Section.TLabelframe")
        summary_frame.pack(fill="x", padx=8, pady=(8, 4))
        self.lbl_executive_summary = ttk.Label(summary_frame, text="Noch keine Analyse ausgeführt.", justify="left")
        self.lbl_executive_summary.pack(anchor="w", padx=8, pady=(6, 4))
        ttk.Label(summary_frame, textvariable=self._report_verweis_var, style="Subheadline.TLabel").pack(
            anchor="w", padx=8, pady=(0, 6)
        )

        self.tree_ergebnisse = ttk.Treeview(frame, columns=("details",), show="tree headings", height=10)
        self.tree_ergebnisse.heading("#0", text="Server / Kurzstatus")
        self.tree_ergebnisse.heading("details", text="Detailansicht")
        self.tree_ergebnisse.column("#0", width=320)
        self.tree_ergebnisse.column("details", width=720)
        self.tree_ergebnisse.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree_ergebnisse.yview)
        scrollbar.pack(side="right", fill="y", pady=8, padx=8)
        self.tree_ergebnisse.configure(yscrollcommand=scrollbar.set)

    def _aktualisiere_button_zustaende(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        """Aktiviert oder deaktiviert Aktionen abhängig vom aktuellen GUI-Zustand."""
        servername = self.entry_servername.get().strip()
        hat_server = bool(servername)
        self.btn_hinzufuegen.configure(state="normal" if hat_server else "disabled")

        hat_zeilen = bool(self._zeilen_nach_id)
        hat_auswahl = bool(self.tree.selection())
        self.btn_analyse.configure(state="normal" if hat_zeilen else "disabled")
        self.btn_loeschen.configure(state="normal" if hat_auswahl else "disabled")

    def _lade_serverliste_aus_status(self) -> None:
        """Stellt gespeicherte Serverlisten beim Start der GUI wieder her."""
        gespeicherte_zeilen = self.modulzustand.get("serverlisten", [])
        for zeile_dict in gespeicherte_zeilen:
            try:
                self._fuege_zeile_ein(ServerTabellenZeile(**zeile_dict))
            except TypeError:
                logger.warning("Ungültiger Servereintrag in gui_state.json wurde übersprungen: %s", zeile_dict)

    def _exists_server(self, servername: str) -> bool:
        suchwert = normalisiere_servernamen(servername)
        return any(normalisiere_servernamen(zeile.servername) == suchwert for zeile in self._zeilen_nach_id.values())

    def _fuege_zeile_ein(self, zeile: ServerTabellenZeile) -> None:
        if self._exists_server(zeile.servername):
            logger.info("Server %s wird wegen Duplikat ignoriert.", zeile.servername)
            return

        item_id = self.tree.insert(
            "",
            "end",
            values=(
                zeile.servername,
                _checkbox_wert(zeile.sql),
                _checkbox_wert(zeile.app),
                _checkbox_wert(zeile.ctx),
                zeile.quelle,
                zeile.status,
            ),
        )
        self._zeilen_nach_id[item_id] = zeile
        self._aktualisiere_button_zustaende()

    def _toggle_rolle_per_klick(self, event: tk.Event[tk.Misc]) -> None:
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item_id = self.tree.identify_row(event.y)
        spalte = self.tree.identify_column(event.x)
        if not item_id or not spalte:
            return

        spalten_index = int(spalte.replace("#", "")) - 1
        spaltenname = _SPALTEN[spalten_index]
        if spaltenname not in _ROLLEN_SPALTEN:
            return

        zeile = self._zeilen_nach_id[item_id]
        attribut = _ROLLEN_SPALTEN[spaltenname]
        neuer_wert = not getattr(zeile, attribut)
        setattr(zeile, attribut, neuer_wert)
        if zeile.auto_rolle:
            zeile.manuell_ueberschrieben = True
        self.tree.set(item_id, spaltenname, _checkbox_wert(neuer_wert))

    def server_manuell_hinzufuegen(self) -> None:
        servername = self.entry_servername.get().strip()
        if not servername:
            self.shell.zeige_warnung("Eingabe fehlt", "Bitte einen Servernamen eingeben.", "Erfassen Sie einen Zielserver und versuchen Sie es erneut.")
            return

        self._fuege_zeile_ein(
            ServerTabellenZeile(
                servername=servername,
                sql=self.var_sql.get(),
                app=self.var_app.get(),
                ctx=self.var_ctx.get(),
                quelle="manuell",
                status="bereit",
            )
        )
        self.entry_servername.delete(0, tk.END)
        self.shell.setze_status("Server wurde hinzugefügt")
        self._aktualisiere_button_zustaende()

    def _entferne_fehler_markierung(self, event: tk.Event[tk.Misc]) -> None:
        """Setzt die Standarddarstellung eines zuvor als fehlerhaft markierten Feldes zurück."""
        event.widget.configure(highlightthickness=0)

    def _markiere_fehlerhaftes_feld(self, feld: ttk.Entry) -> None:
        """Hebt ein Eingabefeld visuell hervor, damit der Anwender die Ursache schnell erkennt."""
        feld.configure(highlightbackground="#DC2626", highlightcolor="#DC2626", highlightthickness=2)

    def _validiere_discovery_eingaben(self) -> tuple[str, int, int] | None:
        """Validiert Discovery-Parameter und liefert bei Erfolg normalisierte Werte zurück."""
        self._discovery_validierung_hinweis_var.set("")
        for feld in (self.entry_discovery_basis, self.entry_discovery_start, self.entry_discovery_ende):
            feld.configure(highlightthickness=0)

        basis = self._discovery_basis_var.get().strip()
        start_text = self._discovery_start_var.get().strip()
        ende_text = self._discovery_ende_var.get().strip()

        if not _IPV4_BASIS_REGEX.fullmatch(basis):
            self._markiere_fehlerhaftes_feld(self.entry_discovery_basis)
            self._discovery_validierung_hinweis_var.set("Ungültige IPv4-Basis. Erwartetes Format: z. B. 192.168.178")
            return None

        try:
            startwert = int(start_text)
        except ValueError:
            self._markiere_fehlerhaftes_feld(self.entry_discovery_start)
            self._discovery_validierung_hinweis_var.set("Start-Host muss eine Zahl zwischen 0 und 255 sein.")
            return None

        try:
            endwert = int(ende_text)
        except ValueError:
            self._markiere_fehlerhaftes_feld(self.entry_discovery_ende)
            self._discovery_validierung_hinweis_var.set("End-Host muss eine Zahl zwischen 0 und 255 sein.")
            return None

        if not 0 <= startwert <= 255:
            self._markiere_fehlerhaftes_feld(self.entry_discovery_start)
            self._discovery_validierung_hinweis_var.set("Start-Host liegt außerhalb des gültigen Bereichs (0–255).")
            return None

        if not 0 <= endwert <= 255:
            self._markiere_fehlerhaftes_feld(self.entry_discovery_ende)
            self._discovery_validierung_hinweis_var.set("End-Host liegt außerhalb des gültigen Bereichs (0–255).")
            return None

        if startwert > endwert:
            self._markiere_fehlerhaftes_feld(self.entry_discovery_start)
            self._markiere_fehlerhaftes_feld(self.entry_discovery_ende)
            self._discovery_validierung_hinweis_var.set("Start-Host darf nicht größer als End-Host sein.")
            return None

        return basis, startwert, endwert

    def discovery_starten(self) -> None:
        if not self.shell.bestaetige_aktion("Discovery bestätigen", "Die Netzwerk-Discovery wird gestartet."):
            return

        validierte_eingabe = self._validiere_discovery_eingaben()
        if not validierte_eingabe:
            self.shell.zeige_warnung(
                "Ungültige Discovery-Eingaben",
                "Bitte korrigieren Sie die markierten Felder.",
                "Nutzen Sie das Beispiel unter den Feldern als Eingabehilfe.",
            )
            return

        basis, startwert, endwert = validierte_eingabe
        self._letzte_discovery_range.set(f"{basis}.{startwert}-{endwert}")
        self.shell.setze_status("Discovery läuft")
        self.master.update_idletasks()

        try:
            treffer = entdecke_server_ergebnisse(
                basis=basis.strip(),
                start=startwert,
                ende=endwert,
                konfiguration=DiscoveryKonfiguration(nutze_reverse_dns=True, nutze_ad_ldap=True),
            )
        except Exception as exc:  # noqa: BLE001 - robuste GUI-Fehlerbehandlung.
            logger.exception("Discovery fehlgeschlagen")
            self.shell.zeige_fehler("Discovery-Fehler", f"Discovery konnte nicht ausgeführt werden: {exc}", "Prüfen Sie Netzwerkbereich und Berechtigungen.")
            self.shell.setze_status("Discovery fehlgeschlagen")
            return

        dialog = DiscoveryTrefferDialog(self.master, treffer)
        self.master.wait_window(dialog.window)

        hinzugefuegt = 0
        for auswahl in dialog.ausgewaehlt:
            vorher = len(self._zeilen_nach_id)
            auto_rollen = _rollen_aus_discovery_treffer(auswahl)
            auto_rolle = ", ".join(auto_rollen)
            self._fuege_zeile_ein(
                ServerTabellenZeile(
                    servername=auswahl.hostname,
                    quelle="Discovery",
                    status="bereit",
                    sql="SQL" in auto_rollen,
                    app="APP" in auto_rollen,
                    ctx="CTX" in auto_rollen,
                    auto_rolle=auto_rolle,
                )
            )
            if len(self._zeilen_nach_id) > vorher:
                hinzugefuegt += 1

        self.shell.zeige_erfolg(
            "Discovery abgeschlossen",
            f"Gefundene Treffer: {len(treffer)}\nAusgewählt: {len(dialog.ausgewaehlt)}\nNeu übernommen: {hinzugefuegt}",
            "Prüfen Sie die Serverliste und passen Sie Rollen bei Bedarf an.",
        )
        self.shell.setze_status("Discovery abgeschlossen")
        self._aktualisiere_button_zustaende()

    def eintrag_loeschen(self) -> None:
        auswahl = self.tree.selection()
        if not auswahl:
            return

        for item_id in auswahl:
            self._zeilen_nach_id.pop(item_id, None)
            self.tree.delete(item_id)
        self.shell.setze_status("Ausgewählte Einträge gelöscht")
        self._aktualisiere_button_zustaende()

    def _zeige_ergebnisse_aufklappbar(self, ergebnisse: list[AnalyseErgebnis]) -> None:
        for item_id in self.tree_ergebnisse.get_children(""):
            self.tree_ergebnisse.delete(item_id)

        self.lbl_executive_summary.configure(text="\n".join(_baue_executive_summary(ergebnisse)))

        for ergebnis in ergebnisse:
            server_knoten = self.tree_ergebnisse.insert(
                "",
                "end",
                text=ergebnis.server,
                values=(_kurzstatus(ergebnis),),
                open=False,
            )
            for detail in _detailzeilen(ergebnis):
                self.tree_ergebnisse.insert(server_knoten, "end", text="Überblick", values=(detail,))

            drilldown = _drilldown_knoten(ergebnis)
            for kategorie, eintraege in drilldown.items():
                kategorie_knoten = self.tree_ergebnisse.insert(server_knoten, "end", text=kategorie, values=("",), open=False)
                for eintrag in eintraege:
                    self.tree_ergebnisse.insert(kategorie_knoten, "end", text="", values=(eintrag,))

    def _setze_server_status(self, status: str) -> None:
        for item_id, zeile in self._zeilen_nach_id.items():
            zeile.status = status
            self.tree.set(item_id, _SPALTE_STATUS, status)

    def analyse_starten(self) -> None:
        zeilen = list(self._zeilen_nach_id.values())
        ziele = _baue_serverziele(zeilen)
        if not ziele:
            self.shell.zeige_warnung("Keine Server", "Bitte mindestens einen gültigen Server hinzufügen.", "Fügen Sie mindestens einen Server in der Liste hinzu.")
            return

        bestaetigt = self.shell.bestaetige_aktion("Analyse bestätigen", _deklarationszusammenfassung(ziele, zeilen))
        if not bestaetigt:
            return

        self._setze_server_status("Analyse läuft")
        self.shell.setze_status("Analyse läuft")
        self.master.update_idletasks()

        try:
            lauf_id = erstelle_lauf_id()
            setze_lauf_id(lauf_id)
            self.shell.setze_lauf_id(lauf_id)
            ergebnisse = analysiere_mehrere_server(ziele, lauf_id=lauf_id)
        except Exception as exc:  # noqa: BLE001 - GUI soll Fehler anzeigen statt abzubrechen.
            logger.exception("Mehrserveranalyse fehlgeschlagen")
            self.shell.zeige_fehler("Analysefehler", f"Mehrserveranalyse fehlgeschlagen: {exc}", "Prüfen Sie die Logs und wiederholen Sie die Analyse.")
            self._setze_server_status("fehlerhaft")
            self.shell.setze_status("Analyse fehlgeschlagen")
            return

        self._letzte_ergebnisse = ergebnisse
        status_nach_server = {normalisiere_servernamen(ergebnis.server): "analysiert" for ergebnis in ergebnisse}
        for item_id, zeile in self._zeilen_nach_id.items():
            zeile.status = status_nach_server.get(normalisiere_servernamen(zeile.servername), "unbekannt")
            self.tree.set(item_id, _SPALTE_STATUS, zeile.status)

        self._zeige_ergebnisse_aufklappbar(ergebnisse)

        report_pfad = self._ausgabe_pfad.get().strip() or "docs/serverbericht.md"
        try:
            export_pfad, export_zeitpunkt = _schreibe_analyse_report(ergebnisse, report_pfad)
            self._letzter_export_pfad = export_pfad
            self._letzter_exportzeitpunkt = export_zeitpunkt
            self._letzte_export_lauf_id = lauf_id
            self._report_verweis_var.set(
                _baue_report_verweistext(self._letzter_export_pfad, self._letzter_exportzeitpunkt, self._letzte_export_lauf_id)
            )
            self.shell.logge_meldung(f"Analysebericht erzeugt: {export_pfad}")
        except Exception as exc:  # noqa: BLE001 - Analyseergebnis bleibt nutzbar, auch wenn Export fehlschlägt.
            logger.exception("Analysebericht konnte nicht geschrieben werden")
            self.shell.zeige_warnung(
                "Exportwarnung",
                f"Analyse war erfolgreich, aber der Report konnte nicht geschrieben werden: {exc}",
                "Prüfen Sie den Ausgabepfad und Dateiberechtigungen.",
            )

        self.shell.setze_status("Analyse abgeschlossen")
        self.shell.logge_meldung(f"Analyse abgeschlossen. Lauf-ID: {self.shell.lauf_id_var.get()}")
        self.speichern()
        self.shell.zeige_erfolg("Analyse abgeschlossen", "Die Mehrserveranalyse wurde erfolgreich abgeschlossen.", "Öffnen Sie die Ergebnisdetails oder starten Sie den nächsten Lauf.")

    def _baue_kerninfos(self) -> list[str]:
        """Erzeugt kompakte Übersichtsinfos für die Übersichtsseite im Launcher."""
        if not self._letzte_ergebnisse:
            return [f"Server in Liste: {len(self._zeilen_nach_id)}"]

        servernamen = ", ".join(ergebnis.server for ergebnis in self._letzte_ergebnisse[:3])
        return [
            f"Analysierte Server: {len(self._letzte_ergebnisse)}",
            f"Beispiele: {servernamen}",
            f"Discovery-Range: {self._letzte_discovery_range.get() or 'nicht gesetzt'}",
        ]

    def speichern(self) -> None:
        """Persistiert Serverlisten, Rollen, Discovery-Range und Ausgabepfade."""
        serverlisten = [asdict(zeile) for zeile in self._zeilen_nach_id.values()]
        rollen = {zeile.servername: zeile.rollen() for zeile in self._zeilen_nach_id.values()}
        ausgabepfade = {
            "analyse_report": self._ausgabe_pfad.get().strip() or "docs/serverbericht.md",
            "log_report": "logs/log_dokumentation.md",
        }

        self.modulzustand.update(
            {
                "serverlisten": serverlisten,
                "rollen": rollen,
                "letzte_discovery_range": self._letzte_discovery_range.get().strip(),
                "letzte_discovery_eingabe": {
                    "basis": self._discovery_basis_var.get().strip(),
                    "start": self._discovery_start_var.get().strip(),
                    "ende": self._discovery_ende_var.get().strip(),
                },
                "ausgabepfade": ausgabepfade,
                "letzte_kerninfos": self._baue_kerninfos(),
                "bericht_verweise": [ausgabepfade["analyse_report"], ausgabepfade["log_report"]],
                "letzter_exportpfad": self._letzter_export_pfad,
                "letzter_exportzeitpunkt": self._letzter_exportzeitpunkt,
                "letzte_export_lauf_id": self._letzte_export_lauf_id,
            }
        )
        self.state_store.speichere_modulzustand("server_analysis", self.modulzustand)
        self.shell.setze_status("Zustand gespeichert")
        self.shell.logge_meldung(f"Persistiert nach: {self.state_store.dateipfad}")

    def _zurueck(self) -> None:
        """Navigationsaktion: in dieser Ansicht entspricht Zurück dem Schließen."""
        self.master.destroy()


def start_gui() -> None:
    """Programmatischer Einstiegspunkt für die Mehrserver-GUI."""
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    MehrserverAnalyseGUI(root)
    root.mainloop()


def main() -> None:
    """CLI-kompatibler Startpunkt mit Installationsschutz."""

    def _zeige_fehler(text: str) -> None:
        print(f"❌ {text}")

    def _frage_installation(_frage: str) -> bool:
        antwort = input("Installation starten? [j/N]: ").strip().lower()
        return antwort in {"j", "ja", "y", "yes"}

    freigegeben = verarbeite_installations_guard(
        pruefe_installationszustand(),
        modulname="Serveranalyse",
        fehlermeldung_fn=_zeige_fehler,
        installationsfrage_fn=_frage_installation,
    )
    if not freigegeben:
        return

    start_gui()


if __name__ == "__main__":
    main()
