"""Mehrserver-GUI für die Serveranalyse mit gemeinsamem Shell-Konzept."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re
import tkinter as tk
from tkinter import simpledialog, ttk

from systemmanager_sagehelper.analyzer import (
    analysiere_mehrere_server,
    DiscoveryKonfiguration,
    entdecke_server_ergebnisse,
    entdecke_server_namen,
)
from systemmanager_sagehelper.gui_shell import GuiShell
from systemmanager_sagehelper.installation_state import pruefe_installationszustand, verarbeite_installations_guard
from systemmanager_sagehelper.gui_state import GUIStateStore
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from systemmanager_sagehelper.models import AnalyseErgebnis, DiscoveryErgebnis, ServerDetailkarte, ServerZiel
from systemmanager_sagehelper.config import STANDARD_PORTS
from systemmanager_sagehelper.report import render_markdown
from systemmanager_sagehelper.viewmodel import baue_server_detailkarte, baue_server_detailkarten
from systemmanager_sagehelper.targeting import normalisiere_servernamen, rollen_aus_bool_flags
from systemmanager_sagehelper.texte import (
    BERICHT_MANAGEMENT_ZUSAMMENFASSUNG,
    BUTTON_ANALYSE_STARTEN,
    BUTTON_NETZWERKERKENNUNG_STARTEN,
)


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
    aufgeloester_hostname: str = ""
    ip_adresse: str = ""
    namensquelle: str = ""
    erreichbarkeitsstatus: str = ""
    vertrauensgrad: float = 0.0

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
    if zeile.quelle.lower() in {"discovery", "netzwerkerkennung", "automatisch erkannt"} and not zeile.manuell_ueberschrieben:
        return "automatisch erkannt"
    if zeile.manuell_ueberschrieben:
        return "manuell angepasst"
    return "manuell gesetzt"


def _deklarationszusammenfassung(ziele: list[ServerZiel], zeilen: list[ServerTabellenZeile]) -> str:
    """Erzeugt eine lesbare Zusammenfassung vor Ausführung der Analyse."""
    quelle_pro_server = {normalisiere_servernamen(zeile.servername): zeile.quelle for zeile in zeilen}
    zusammenfassung = ["So wurden die Server deklariert:"]
    for index, ziel in enumerate(ziele, start=1):
        rollen = ", ".join(ziel.rollen) if ziel.rollen else "keine Rolle gesetzt"
        quelle_roh = quelle_pro_server.get(normalisiere_servernamen(ziel.name), "unbekannt")
        quelle = "Netzwerkerkennung" if quelle_roh.lower() == "discovery" else quelle_roh
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
    """Erzeugt einen klaren Verweistext für die GUI nach Bericht-Export."""
    if not exportpfad:
        return "Kein Analysebericht erstellt."
    zeit = exportzeitpunkt or "Zeitpunkt unbekannt"
    lauf = lauf_id or "Lauf-ID unbekannt"
    return f"Letzter Analysebericht: {exportpfad} | Exportzeit: {zeit} | Lauf-ID: {lauf}"


def _ist_server_erreichbar(ergebnis: AnalyseErgebnis) -> bool:
    """Leitet den Erreichbarkeitsstatus robust aus dem Analyseergebnis ab."""
    return any(port.offen for port in ergebnis.ports)


def _baue_server_summary(ergebnisse: list[AnalyseErgebnis]) -> list[dict[str, object]]:
    """Erstellt eine persistierbare Kurzstruktur je Server für Dashboard und Modulzustand."""
    server_summary: list[dict[str, object]] = []
    for ergebnis in ergebnisse:
        server_summary.append(
            {
                "name": ergebnis.server,
                "erreichbar": _ist_server_erreichbar(ergebnis),
                "rollen": ergebnis.rollen,
                "rollenquelle": ergebnis.rollenquelle or "unbekannt",
                "letzte_pruefung": ergebnis.zeitpunkt.isoformat(timespec="seconds"),
            }
        )
    return server_summary


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
    rollenhinweise: tuple[str, ...] = ()
    namensquelle: str | None = None
    erklaerung: str = ""


def _bewerte_vertrauen_als_sterne(vertrauensgrad: float) -> str:
    """Wandelt den Rohwert (0.0-1.0) in eine 5-Sterne-Skala um."""
    begrenzt = max(0.0, min(1.0, vertrauensgrad))
    aktive_sterne = round(begrenzt * 5)
    return "★" * aktive_sterne + "☆" * (5 - aktive_sterne)


def _formatiere_vertrauensanzeige(vertrauensgrad: float, *, zeige_rohwert: bool) -> str:
    """Erzeugt den Anzeige-Text für die Vertrauensspalte."""
    sterne = _bewerte_vertrauen_als_sterne(vertrauensgrad)
    if not zeige_rohwert:
        return sterne
    return f"{sterne} ({vertrauensgrad:.2f})"


def _namensquelle_anzeige(namensquelle: str | None) -> str:
    """Formatiert die Herkunft des angezeigten Hostnamens für die GUI."""
    mapping = {
        "forward_dns": "Forward-DNS",
        "reverse_dns": "Reverse-DNS",
        "eingabe": "Eingabe",
    }
    return mapping.get((namensquelle or "").lower(), "nicht auflösbar")


def _erklaerung_aus_treffer(treffer: DiscoveryTabellenTreffer) -> str:
    """Erstellt eine knappe Begründung für den Rollenvorschlag."""
    teile = []
    if treffer.dienste and treffer.dienste != "-":
        teile.append(f"Ports/Dienste: {treffer.dienste}")
    if treffer.rollenhinweise:
        teile.append("Hinweise: " + ", ".join(treffer.rollenhinweise))
    teile.append(f"Hostname: {_namensquelle_anzeige(treffer.namensquelle)}")
    return " | ".join(teile)


_VERTRAUENS_TOOLTIP_TEXT = (
    "Bewertungslogik des Vertrauensgrads:\n"
    "• ICMP-Erreichbarkeit: +0,45\n"
    "• TCP-Anteil: +0,10 je erkanntem Dienst (max. +0,40)\n"
    "• Reverse-DNS-Anteil: +0,10\n"
    "• AD-Anteil (LDAP-Hinweis): +0,05\n"
    "• Gesamtwert wird auf 1,00 begrenzt"
)


class _TooltipHelfer:
    """Einfacher Tooltip-Helfer für Widgets ohne eingebauten Tooltip-Support."""

    def __init__(self, parent: tk.Misc) -> None:
        self._parent = parent
        self._tooltip: tk.Toplevel | None = None
        self._label: ttk.Label | None = None

    def zeige(self, *, x: int, y: int, text: str) -> None:
        """Blendet den Tooltip an den übergebenen Bildschirmkoordinaten ein."""
        if self._tooltip is None:
            self._tooltip = tk.Toplevel(self._parent)
            self._tooltip.wm_overrideredirect(True)
            self._label = ttk.Label(
                self._tooltip,
                text=text,
                justify="left",
                relief="solid",
                borderwidth=1,
                padding=(8, 6),
            )
            self._label.pack()
        elif self._label is not None:
            self._label.configure(text=text)

        # Leichter Versatz, damit der Cursor den Tooltip nicht direkt überdeckt.
        self._tooltip.wm_geometry(f"+{x + 14}+{y + 16}")
        self._tooltip.deiconify()

    def ausblenden(self) -> None:
        """Versteckt den Tooltip, falls er aktuell sichtbar ist."""
        if self._tooltip is not None:
            self._tooltip.withdraw()




def _filter_discovery_treffer(
    treffer_liste: list[DiscoveryTabellenTreffer],
    *,
    filtertext: str,
    nur_erreichbare: bool,
) -> list[DiscoveryTabellenTreffer]:
    """Filtert Discovery-Treffer nach Suchtext und Erreichbarkeit.

    Nicht erreichbare Treffer werden standardmäßig ausgeblendet, wenn
    ``nur_erreichbare`` aktiv ist.
    """
    suchbegriff = filtertext.strip().lower()
    gefiltert: list[DiscoveryTabellenTreffer] = []
    for treffer in treffer_liste:
        if nur_erreichbare and not treffer.erreichbar:
            continue
        if suchbegriff and suchbegriff not in treffer.hostname.lower() and suchbegriff not in treffer.ip_adresse.lower():
            continue
        gefiltert.append(treffer)
    return gefiltert

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
                rollenhinweise=tuple(item.rollenhinweise),
                namensquelle=item.namensquelle,
                erklaerung="",
            )
            for item in treffer
        ]
        for eintrag in self._treffer:
            eintrag.erklaerung = _erklaerung_aus_treffer(eintrag)
        self.ausgewaehlt: list[DiscoveryTabellenTreffer] = []

        self.window = tk.Toplevel(parent)
        self.window.title("Discovery-Treffer prüfen")
        self.window.geometry("900x520")
        self.window.transient(parent)
        self.window.grab_set()

        self.filter_var = tk.StringVar(value="")
        self.filter_var.trace_add("write", lambda *_: self._render_treffer())
        # Standardfilter: Fokus auf tatsächlich erreichbare Systeme.
        self.nur_erreichbare_var = tk.BooleanVar(value=True)
        self.zeige_rohwert_var = tk.BooleanVar(value=False)
        self._tooltip_helfer = _TooltipHelfer(self.window)

        kopf = ttk.Frame(self.window)
        kopf.pack(fill="x", padx=8, pady=8)
        ttk.Label(kopf, text="Filter (Hostname/IP):").pack(side="left")
        ttk.Entry(kopf, textvariable=self.filter_var, width=30).pack(side="left", padx=6)
        ttk.Checkbutton(
            kopf,
            text="Nur erreichbare Server anzeigen",
            variable=self.nur_erreichbare_var,
            command=self._render_treffer,
        ).pack(side="left", padx=(8, 4))
        ttk.Checkbutton(
            kopf,
            text="Rohwert zusätzlich anzeigen",
            variable=self.zeige_rohwert_var,
            command=self._render_treffer,
        ).pack(side="left", padx=(4, 4))
        hinweis_label = ttk.Label(kopf, text="ℹ Bewertungslogik", cursor="hand2")
        hinweis_label.pack(side="left", padx=(6, 4))
        hinweis_label.bind("<Enter>", self._zeige_vertrauenstooltip)
        hinweis_label.bind("<Leave>", lambda *_: self._tooltip_helfer.ausblenden())
        hinweis_label.bind("<Motion>", self._bewege_vertrauenstooltip)
        ttk.Button(kopf, text="Alle auswählen", command=self._waehle_alle).pack(side="left", padx=4)
        ttk.Button(kopf, text="Auswahl übernehmen", command=self._uebernehmen).pack(side="right", padx=4)

        self.tree = ttk.Treeview(
            self.window,
            columns=("hostname", "ip", "erreichbar", "dienste", "namensquelle", "vertrauen", "erklaerung"),
            show="headings",
            selectmode="extended",
            height=17,
        )
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.heading("hostname", text="Hostname (bearbeitbar)")
        self.tree.heading("ip", text="IP")
        self.tree.heading("erreichbar", text="Erreichbar")
        self.tree.heading("dienste", text="Dienste")
        self.tree.heading("namensquelle", text="Namensquelle")
        self.tree.heading("vertrauen", text="Vertrauensgrad")
        self.tree.heading("erklaerung", text="Erklärung")
        self.tree.column("hostname", width=220)
        self.tree.column("ip", width=150)
        self.tree.column("erreichbar", width=90, anchor="center")
        self.tree.column("dienste", width=180)
        self.tree.column("namensquelle", width=120, anchor="center")
        self.tree.column("vertrauen", width=150, anchor="center")
        self.tree.column("erklaerung", width=320)
        self.tree.bind("<Double-1>", self._bearbeite_hostname)

        self._id_zu_treffer: dict[str, DiscoveryTabellenTreffer] = {}
        self._render_treffer()

    def _render_treffer(self) -> None:
        for item_id in self.tree.get_children(""):
            self.tree.delete(item_id)
        self._id_zu_treffer.clear()

        gefilterte_treffer = _filter_discovery_treffer(
            self._treffer,
            filtertext=self.filter_var.get(),
            nur_erreichbare=self.nur_erreichbare_var.get(),
        )
        for treffer in gefilterte_treffer:
            item_id = self.tree.insert(
                "",
                "end",
                values=(
                    treffer.hostname,
                    treffer.ip_adresse,
                    "ja" if treffer.erreichbar else "nein",
                    treffer.dienste,
                    _namensquelle_anzeige(treffer.namensquelle),
                    _formatiere_vertrauensanzeige(
                        treffer.vertrauensgrad,
                        zeige_rohwert=self.zeige_rohwert_var.get(),
                    ),
                    treffer.erklaerung,
                ),
            )
            self._id_zu_treffer[item_id] = treffer


    def _zeige_vertrauenstooltip(self, event: tk.Event[tk.Misc]) -> None:
        """Zeigt den Tooltip zur Vertrauensbewertung an."""
        self._tooltip_helfer.zeige(x=event.x_root, y=event.y_root, text=_VERTRAUENS_TOOLTIP_TEXT)

    def _bewege_vertrauenstooltip(self, event: tk.Event[tk.Misc]) -> None:
        """Aktualisiert die Tooltip-Position während der Mausbewegung."""
        self._tooltip_helfer.zeige(x=event.x_root, y=event.y_root, text=_VERTRAUENS_TOOLTIP_TEXT)

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
    """Leitet Rollenvorschläge über gewichtete Heuristiken aus Discovery-Indikatoren ab."""
    punktestand = {"SQL": 0, "APP": 0, "CTX": 0}

    # Port-/Dienstgewichtung: SQL bleibt auch ohne offenen 1433 möglich.
    if any(port in treffer.dienste for port in ("1433", "1434", "4022")):
        punktestand["SQL"] += 4
    if "3389" in treffer.dienste:
        punktestand["CTX"] += 4

    # Analysevorbefunde aus Discovery (z. B. Remote-Inventar, SQL-Dienste, Instanzen).
    for hinweis in treffer.rollenhinweise:
        lower = hinweis.lower()
        if lower.startswith("sql_"):
            punktestand["SQL"] += 3
        if "termservice" in lower or "sessionenv" in lower:
            punktestand["CTX"] += 2

    # Restliche erreichbare Systeme werden als APP gewichtet, aber nicht blind bevorzugt.
    if treffer.erreichbar:
        punktestand["APP"] += 1

    rollen = [rolle for rolle, score in punktestand.items() if score >= 3]
    if not rollen:
        # Fallback mit höchstem Score statt starrem APP-Default.
        beste_rolle = max(punktestand, key=punktestand.get)
        rollen = [beste_rolle]
    return rollen
def _detailzeilen(ergebnis: AnalyseErgebnis) -> list[str]:
    """Liefert einen kompakten Freitext-Überblick als Ergänzung zur Detailkarte."""
    karte = baue_server_detailkarte(ergebnis)
    details: list[str] = [
        f"Betriebssystem: {karte.betriebssystem or 'unbekannt'} ({karte.os_version or 'unbekannt'})",
        f"Rollenquelle: {karte.rollenquelle or 'unbekannt'}",
    ]

    for check in karte.rollen_checks:
        status = "erkannt" if check.erkannt else "nicht erkannt"
        details.append(f"{check.rolle}-Prüfung: {status} | {' | '.join(check.details)}")

    if karte.freitext_hinweise:
        details.append("Hinweise:")
        details.extend(f"- {hinweis}" for hinweis in karte.freitext_hinweise)
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
            untertitel="Zielserver erfassen, Netzwerkerkennung ausführen und Analyseergebnisse auswerten",
            on_save=self.speichern,
            on_back=self._zurueck,
            on_exit=self.master.destroy,
        )

        self._zeilen_nach_id: dict[str, ServerTabellenZeile] = {}
        self._letzte_ergebnisse: list[AnalyseErgebnis] = []
        # Strukturierte Detailkarten dienen als gemeinsame Datenbasis für Tabs und Reporting.
        self._detailkarten: list[ServerDetailkarte] = []
        self._server_auswahl_var = tk.StringVar(value="")
        # Strukturierter Snapshot der letzten Analyse für modulübergreifende Übersichten.
        self._server_summary: list[dict[str, object]] = self.modulzustand.get("server_summary", [])
        self._letzte_discovery_range = tk.StringVar(value=self.modulzustand.get("letzte_discovery_range", ""))
        self._letzter_discovery_modus = tk.StringVar(value=self.modulzustand.get("letzter_discovery_modus", "range"))
        self._letzte_discovery_namen = tk.StringVar(value=self.modulzustand.get("letzte_discovery_namen", ""))
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

        ttk.Label(form_frame, text="Letzter Netzwerkerkennungs-Bereich:").grid(row=4, column=0, sticky="w", padx=8, pady=(2, 8))
        ttk.Entry(form_frame, textvariable=self._letzte_discovery_range, width=30).grid(row=4, column=1, padx=6, sticky="w")

        ttk.Label(form_frame, text="Servernamenliste (eine Zeile pro Host):").grid(row=5, column=0, sticky="nw", padx=8, pady=(2, 8))
        self.text_discovery_namen = tk.Text(form_frame, width=45, height=5, wrap="none")
        self.text_discovery_namen.grid(row=5, column=1, columnspan=5, padx=6, pady=(2, 8), sticky="we")
        self.text_discovery_namen.insert("1.0", self._letzte_discovery_namen.get())

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
            action_frame, text=BUTTON_NETZWERKERKENNUNG_STARTEN, style="Secondary.TButton", command=self.discovery_starten
        )
        self.btn_discovery.pack(side="left", padx=4)
        self.btn_discovery_namen = ttk.Button(
            action_frame,
            text="Servernamen prüfen",
            style="Secondary.TButton",
            command=self.discovery_servernamen_starten,
        )
        self.btn_discovery_namen.pack(side="left", padx=4)
        self.btn_loeschen = ttk.Button(
            action_frame,
            text="Ausgewählten Eintrag löschen",
            style="Secondary.TButton",
            command=self.eintrag_loeschen,
            state="disabled",
        )
        self.btn_loeschen.pack(side="left", padx=4)
        self.btn_analyse = ttk.Button(
            action_frame, text=BUTTON_ANALYSE_STARTEN, style="Primary.TButton", command=self.analyse_starten, state="disabled"
        )
        self.btn_analyse.pack(side="right", padx=4)

    def _baue_ergebnisbereich(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Analyseergebnis je Server", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)

        summary_frame = ttk.LabelFrame(frame, text=BERICHT_MANAGEMENT_ZUSAMMENFASSUNG, style="Section.TLabelframe")
        summary_frame.pack(fill="x", padx=8, pady=(8, 4))
        self.lbl_executive_summary = ttk.Label(summary_frame, text="Noch keine Analyse durchgeführt.", justify="left")
        self.lbl_executive_summary.pack(anchor="w", padx=8, pady=(6, 4))
        ttk.Label(summary_frame, textvariable=self._report_verweis_var, style="Subheadline.TLabel").pack(
            anchor="w", padx=8, pady=(0, 6)
        )

        auswahl_frame = ttk.Frame(frame)
        auswahl_frame.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(auswahl_frame, text="Serverauswahl:").pack(side="left")
        self.cmb_serverauswahl = ttk.Combobox(
            auswahl_frame,
            textvariable=self._server_auswahl_var,
            state="readonly",
            values=[],
            width=42,
        )
        self.cmb_serverauswahl.pack(side="left", padx=(8, 0))
        self.cmb_serverauswahl.bind("<<ComboboxSelected>>", lambda _event: self._aktualisiere_tab_inhalte())

        self.notebook_ergebnisse = ttk.Notebook(frame)
        self.notebook_ergebnisse.pack(fill="both", expand=True, padx=8, pady=8)

        self.txt_tab_uebersicht = self._erstelle_tab_textfeld("Übersicht")
        self.txt_tab_rollen = self._erstelle_tab_textfeld("Rollen")
        self.txt_tab_ports_dienste = self._erstelle_tab_textfeld("Ports/Dienste")
        self.txt_tab_software = self._erstelle_tab_textfeld("Software")
        self.txt_tab_empfehlungen = self._erstelle_tab_textfeld("Empfehlungen")

    def _erstelle_tab_textfeld(self, titel: str) -> tk.Text:
        """Erstellt ein wiederverwendbares, schreibgeschütztes Textfeld innerhalb eines Ergebnis-Tabs."""
        tab = ttk.Frame(self.notebook_ergebnisse)
        self.notebook_ergebnisse.add(tab, text=titel)
        textfeld = tk.Text(tab, wrap="word", height=10)
        textfeld.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=textfeld.yview)
        scrollbar.pack(side="right", fill="y")
        textfeld.configure(yscrollcommand=scrollbar.set, state="disabled")
        return textfeld

    def _setze_textfeld_inhalt(self, textfeld: tk.Text, zeilen: list[str]) -> None:
        """Schreibt Zeilen konsistent in ein Tab-Textfeld."""
        textfeld.configure(state="normal")
        textfeld.delete("1.0", "end")
        textfeld.insert("1.0", "\n".join(zeilen) if zeilen else "Keine Daten vorhanden.")
        textfeld.configure(state="disabled")

    def _aktualisiere_tab_inhalte(self) -> None:
        """Aktualisiert alle Ergebnis-Tabs anhand der aktuell gewählten Serverkarte."""
        servername = self._server_auswahl_var.get().strip()
        karte = next((eintrag for eintrag in self._detailkarten if eintrag.server == servername), None)
        if not karte:
            for feld in (
                self.txt_tab_uebersicht,
                self.txt_tab_rollen,
                self.txt_tab_ports_dienste,
                self.txt_tab_software,
                self.txt_tab_empfehlungen,
            ):
                self._setze_textfeld_inhalt(feld, ["Noch kein Server ausgewählt."])
            return

        self._setze_textfeld_inhalt(
            self.txt_tab_uebersicht,
            [
                f"Server: {karte.server}",
                f"Zeitpunkt: {karte.zeitpunkt.isoformat(timespec='seconds')}",
                f"Rollen: {', '.join(karte.rollen) if karte.rollen else 'nicht gesetzt'}",
                f"Rollenquelle: {karte.rollenquelle or 'unbekannt'}",
                f"Betriebssystem: {karte.betriebssystem or 'unbekannt'} ({karte.os_version or 'unbekannt'})",
                "",
                "Freitext-Hinweise:",
                *(karte.freitext_hinweise or ["keine"]),
            ],
        )
        self._setze_textfeld_inhalt(
            self.txt_tab_rollen,
            [
                f"{check.rolle}: {'erkannt' if check.erkannt else 'nicht erkannt'} | {' | '.join(check.details)}"
                for check in karte.rollen_checks
            ],
        )
        self._setze_textfeld_inhalt(
            self.txt_tab_ports_dienste,
            [
                f"{eintrag.typ}: {eintrag.name} | Status: {eintrag.status}"
                + (f" | Details: {eintrag.details}" if eintrag.details else "")
                for eintrag in karte.ports_und_dienste
            ],
        )
        self._setze_textfeld_inhalt(self.txt_tab_software, karte.software or ["Keine Software erkannt."])
        self._setze_textfeld_inhalt(self.txt_tab_empfehlungen, karte.empfehlungen or ["Keine Empfehlungen vorhanden."])

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
        if not self.shell.bestaetige_aktion("Netzwerkerkennung bestätigen", "Die Netzwerkerkennung wird gestartet."):
            return

        validierte_eingabe = self._validiere_discovery_eingaben()
        if not validierte_eingabe:
            self.shell.zeige_warnung(
                "Ungültige Eingaben zur Netzwerkerkennung",
                "Bitte korrigieren Sie die markierten Felder.",
                "Nutzen Sie das Beispiel unter den Feldern als Eingabehilfe.",
            )
            return

        basis, startwert, endwert = validierte_eingabe
        self._letzter_discovery_modus.set("range")
        self._letzte_discovery_range.set(f"{basis}.{startwert}-{endwert}")
        self.shell.setze_status("Netzwerkerkennung läuft")
        self.master.update_idletasks()

        try:
            treffer = entdecke_server_ergebnisse(
                basis=basis.strip(),
                start=startwert,
                ende=endwert,
                konfiguration=DiscoveryKonfiguration(nutze_reverse_dns=True, nutze_ad_ldap=True),
            )
        except Exception as exc:  # noqa: BLE001 - robuste GUI-Fehlerbehandlung.
            logger.exception("Netzwerkerkennung fehlgeschlagen")
            self.shell.zeige_fehler("Fehler bei der Netzwerkerkennung", f"Die Netzwerkerkennung konnte nicht ausgeführt werden: {exc}", "Prüfen Sie Netzwerkbereich und Berechtigungen.")
            self.shell.setze_status("Netzwerkerkennung fehlgeschlagen")
            return

        self._uebernehme_discovery_treffer(treffer, erfolgstitel="Netzwerkerkennung abgeschlossen")
        self.shell.setze_status("Netzwerkerkennung abgeschlossen")
        self._aktualisiere_button_zustaende()

    def _lese_discovery_namen_aus_textfeld(self) -> list[str]:
        """Liest die Namenliste robust aus dem Mehrzeilenfeld und entfernt Leerzeilen."""
        text = self.text_discovery_namen.get("1.0", "end").strip()
        self._letzte_discovery_namen.set(text)
        return [zeile.strip() for zeile in text.splitlines() if zeile.strip()]

    def discovery_servernamen_starten(self) -> None:
        """Startet die Discovery gezielt über eine explizite Servernamenliste."""
        if not self.shell.bestaetige_aktion("Servernamen prüfen", "Die Prüfung der Servernamenliste wird gestartet."):
            return

        hosts = self._lese_discovery_namen_aus_textfeld()
        if not hosts:
            self.shell.zeige_warnung(
                "Keine Servernamen angegeben",
                "Bitte tragen Sie mindestens einen Hostnamen in die Servernamenliste ein.",
                "Nutzen Sie pro Zeile genau einen Namen (Kurzname oder FQDN).",
            )
            return

        self._letzter_discovery_modus.set("namenliste")
        self.shell.setze_status("Servernamenprüfung läuft")
        self.master.update_idletasks()

        try:
            treffer = entdecke_server_namen(
                hosts=hosts,
                konfiguration=DiscoveryKonfiguration(nutze_reverse_dns=True, nutze_ad_ldap=True),
            )
        except Exception as exc:  # noqa: BLE001 - robuste GUI-Fehlerbehandlung.
            logger.exception("Servernamenprüfung fehlgeschlagen")
            self.shell.zeige_fehler("Fehler bei der Servernamenprüfung", f"Die Prüfung konnte nicht ausgeführt werden: {exc}", "Prüfen Sie Namensauflösung und Berechtigungen.")
            self.shell.setze_status("Servernamenprüfung fehlgeschlagen")
            return

        self._uebernehme_discovery_treffer(treffer, erfolgstitel="Servernamenprüfung abgeschlossen")
        self.shell.setze_status("Servernamenprüfung abgeschlossen")
        self._aktualisiere_button_zustaende()

    def _uebernehme_discovery_treffer(self, treffer: list[DiscoveryErgebnis], *, erfolgstitel: str) -> None:
        """Zeigt Treffer im Standarddialog und übernimmt ausgewählte Server in die Tabelle."""
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
            erfolgstitel,
            f"Gefundene Treffer: {len(treffer)}\nAusgewählt: {len(dialog.ausgewaehlt)}\nNeu übernommen: {hinzugefuegt}",
            "Prüfen Sie die Serverliste und passen Sie Rollen bei Bedarf an.",
        )

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
        """Aktualisiert Management-Zusammenfassung und Tab-basierte Detailkarten."""
        self.lbl_executive_summary.configure(text="\n".join(_baue_executive_summary(ergebnisse)))
        self._detailkarten = baue_server_detailkarten(ergebnisse)

        servernamen = [karte.server for karte in self._detailkarten]
        self.cmb_serverauswahl.configure(values=servernamen)
        if servernamen:
            self._server_auswahl_var.set(servernamen[0])
        self._aktualisiere_tab_inhalte()

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
        # Unmittelbar nach erfolgreicher Analyse den strukturierten Snapshot aktualisieren.
        self._server_summary = _baue_server_summary(ergebnisse)
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
            self.shell.logge_meldung(f"Analysebericht erstellt: {export_pfad}")
        except Exception as exc:  # noqa: BLE001 - Analyseergebnis bleibt nutzbar, auch wenn Export fehlschlägt.
            logger.exception("Analysebericht konnte nicht geschrieben werden")
            self.shell.zeige_warnung(
                "Exportwarnung",
                f"Analyse war erfolgreich, aber der Bericht konnte nicht geschrieben werden: {exc}",
                "Prüfen Sie den Ausgabepfad und Dateiberechtigungen.",
            )

        self.shell.setze_status("Analyse abgeschlossen")
        self.shell.logge_meldung(f"Analyse abgeschlossen. Lauf-ID: {self.shell.lauf_id_var.get()}")
        self.speichern()
        self.shell.zeige_erfolg("Analyse abgeschlossen", "Die Mehrserveranalyse wurde erfolgreich abgeschlossen.", "Öffnen Sie die Ergebnisdetails oder starten Sie den nächsten Lauf.")

    def _baue_kerninfos(self) -> list[str]:
        """Erzeugt kompakte Übersichtsinfos für die Übersichtsseite im Launcher."""
        if not self._server_summary:
            return [
                "Analyse-Status: Noch keine Analyse vorhanden.",
                f"Server in Liste: {len(self._zeilen_nach_id)}",
                "Führen Sie die Analyse aus, um Rollen und Erreichbarkeit zu sehen.",
            ]

        top_server = self._server_summary[:5]
        statuszeilen = []
        for server in top_server:
            rollen = ", ".join(server.get("rollen", [])) or "keine Rolle"
            status = "erreichbar" if server.get("erreichbar") else "nicht erreichbar"
            statuszeilen.append(f"{server.get('name', 'unbekannt')}: {rollen} ({status})")

        return [
            f"Analyse-Status: {len(self._server_summary)} Server zuletzt geprüft.",
            "Server-Status: " + " | ".join(statuszeilen),
            f"Netzwerkerkennungs-Bereich: {self._letzte_discovery_range.get() or 'nicht gesetzt'}",
        ]

    def speichern(self) -> None:
        """Persistiert Serverlisten, Rollen, Discovery-Range und Ausgabepfade."""
        self._letzte_discovery_namen.set(self.text_discovery_namen.get("1.0", "end").strip())
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
                "letzter_discovery_modus": self._letzter_discovery_modus.get().strip() or "range",
                "letzte_discovery_namen": self._letzte_discovery_namen.get().strip(),
                "letzte_discovery_eingabe": {
                    "basis": self._discovery_basis_var.get().strip(),
                    "start": self._discovery_start_var.get().strip(),
                    "ende": self._discovery_ende_var.get().strip(),
                },
                "ausgabepfade": ausgabepfade,
                "server_summary": self._server_summary,
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
