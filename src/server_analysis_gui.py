"""Mehrserver-GUI für die Serveranalyse.

Dieses Modul stellt eine tabellarische Oberfläche bereit, mit der mehrere Zielserver
inklusive Rollenkennzeichnung verwaltet, per Discovery ergänzt und anschließend
parallel analysiert werden können.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from systemmanager_sagehelper.analyzer import analysiere_mehrere_server, entdecke_server_kandidaten
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id, hole_lauf_id, konfiguriere_logger, setze_lauf_id
from systemmanager_sagehelper.models import AnalyseErgebnis, ServerZiel


@dataclass
class ServerTabellenZeile:
    """Zeilenmodell für die GUI-Tabelle mit Deklaration eines Zielservers."""

    servername: str
    sql: bool = False
    app: bool = True
    ctx: bool = False
    quelle: str = "manuell"
    status: str = "neu"

    def rollen(self) -> list[str]:
        """Leitet die Rollenliste aus den gesetzten Checkboxen ab."""
        rollen: list[str] = []
        if self.sql:
            rollen.append("SQL")
        if self.app:
            rollen.append("APP")
        if self.ctx:
            rollen.append("CTX")
        return rollen


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


logger = konfiguriere_logger(__name__, dateiname="server_analysis_gui.log")


def _normalisiere_servernamen(servername: str) -> str:
    """Normalisiert einen Servernamen für konsistente Duplikatprüfung."""
    return servername.strip().lower()


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
        ziele.append(ServerZiel(name=name, rollen=zeile.rollen()))
    return ziele


def _deklarationszusammenfassung(ziele: list[ServerZiel], zeilen: list[ServerTabellenZeile]) -> str:
    """Erzeugt eine lesbare Zusammenfassung vor Ausführung der Analyse."""
    quelle_pro_server = {_normalisiere_servernamen(zeile.servername): zeile.quelle for zeile in zeilen}
    zusammenfassung = ["So wurden die Server deklariert:"]
    for index, ziel in enumerate(ziele, start=1):
        rollen = ", ".join(ziel.rollen) if ziel.rollen else "keine Rolle gesetzt"
        quelle = quelle_pro_server.get(_normalisiere_servernamen(ziel.name), "unbekannt")
        zusammenfassung.append(f"{index}. {ziel.name} | Rollen: {rollen} | Quelle: {quelle}")
    return "\n".join(zusammenfassung)


def _kurzstatus(ergebnis: AnalyseErgebnis) -> str:
    """Erzeugt einen kompakten Statussatz je Server für die aufklappbare Liste."""
    offene_ports = [str(port.port) for port in ergebnis.ports if port.offen]
    rollen = ", ".join(ergebnis.rollen) if ergebnis.rollen else "nicht gesetzt/ermittelt"
    return f"Rollen: {rollen} | Offene Ports: {', '.join(offene_ports) if offene_ports else 'keine'}"


def _detailzeilen(ergebnis: AnalyseErgebnis) -> list[str]:
    """Liefert strukturierte Detailzeilen je Server für die aufklappbare Ansicht."""
    details: list[str] = [
        f"Betriebssystem: {ergebnis.betriebssystem or 'unbekannt'} ({ergebnis.os_version or 'unbekannt'})",
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
        self.master.title("SystemManager-SageHelper – Mehrserveranalyse")
        self.master.geometry("980x760")

        self._zeilen_nach_id: dict[str, ServerTabellenZeile] = {}
        self._lauf_id_var = tk.StringVar(value=hole_lauf_id())

        self._baue_kopfbereich()
        self._baue_tabelle()
        self._baue_aktionsbereich()
        self._baue_ergebnisbereich()

    def _baue_kopfbereich(self) -> None:
        self.headline = tk.Label(
            self.master,
            text="Mehrserveranalyse",
            font=("Arial", 18, "bold"),
        )
        self.headline.pack(pady=10)

        tk.Label(self.master, text="Lauf-ID:", font=("Arial", 10, "bold")).pack()
        tk.Label(self.master, textvariable=self._lauf_id_var, font=("Consolas", 10)).pack(pady=(0, 8))

        self.form_frame = tk.Frame(self.master)
        self.form_frame.pack(fill="x", padx=12)

        tk.Label(self.form_frame, text="Servername:").grid(row=0, column=0, sticky="w")
        self.entry_servername = tk.Entry(self.form_frame, width=28)
        self.entry_servername.grid(row=0, column=1, padx=6)

        self.var_sql = tk.BooleanVar(value=False)
        self.var_app = tk.BooleanVar(value=True)
        self.var_ctx = tk.BooleanVar(value=False)

        tk.Checkbutton(self.form_frame, text="SQL", variable=self.var_sql).grid(row=0, column=2, padx=4)
        tk.Checkbutton(self.form_frame, text="APP", variable=self.var_app).grid(row=0, column=3, padx=4)
        tk.Checkbutton(self.form_frame, text="CTX", variable=self.var_ctx).grid(row=0, column=4, padx=4)

        tk.Button(
            self.form_frame,
            text="Server manuell hinzufügen",
            command=self.server_manuell_hinzufuegen,
            width=24,
        ).grid(row=0, column=5, padx=8)

    def _baue_tabelle(self) -> None:
        table_frame = tk.Frame(self.master)
        table_frame.pack(fill="both", expand=True, padx=12, pady=10)

        self.tree = ttk.Treeview(table_frame, columns=_SPALTEN, show="headings", height=12)
        self.tree.pack(side="left", fill="both", expand=True)

        spalten_texte = {
            _SPALTE_SERVERNAME: "Servername",
            _SPALTE_SQL: "SQL",
            _SPALTE_APP: "APP",
            _SPALTE_CTX: "CTX",
            _SPALTE_QUELLE: "Quelle",
            _SPALTE_STATUS: "Status",
        }
        for spalte, titel in spalten_texte.items():
            self.tree.heading(spalte, text=titel)

        self.tree.column(_SPALTE_SERVERNAME, width=230)
        self.tree.column(_SPALTE_SQL, width=70, anchor="center")
        self.tree.column(_SPALTE_APP, width=70, anchor="center")
        self.tree.column(_SPALTE_CTX, width=70, anchor="center")
        self.tree.column(_SPALTE_QUELLE, width=130)
        self.tree.column(_SPALTE_STATUS, width=180)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Best-Practice für einfache Bedienung: Klick auf Rollen-Zellen toggelt Checkbox-Zustand.
        self.tree.bind("<Button-1>", self._toggle_rolle_per_klick)

    def _baue_aktionsbereich(self) -> None:
        action_frame = tk.Frame(self.master)
        action_frame.pack(fill="x", padx=12)

        tk.Button(action_frame, text="Discovery", width=18, command=self.discovery_starten).pack(
            side="left", padx=4
        )
        tk.Button(action_frame, text="Ausgewählten Eintrag löschen", width=26, command=self.eintrag_loeschen).pack(
            side="left", padx=4
        )
        tk.Button(
            action_frame,
            text="Analyse starten",
            width=18,
            command=self.analyse_starten,
            bg="#2f8f2f",
            fg="white",
        ).pack(side="right", padx=4)

    def _baue_ergebnisbereich(self) -> None:
        tk.Label(self.master, text="Analyseergebnis je Server (aufklappbar):", font=("Arial", 12, "bold")).pack(
            anchor="w", padx=12
        )

        frame = tk.Frame(self.master)
        frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self.tree_ergebnisse = ttk.Treeview(frame, columns=("details",), show="tree headings", height=11)
        self.tree_ergebnisse.heading("#0", text="Server / Kurzstatus")
        self.tree_ergebnisse.heading("details", text="Detailansicht")
        self.tree_ergebnisse.column("#0", width=320)
        self.tree_ergebnisse.column("details", width=620)
        self.tree_ergebnisse.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree_ergebnisse.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_ergebnisse.configure(yscrollcommand=scrollbar.set)

    def _exists_server(self, servername: str) -> bool:
        suchwert = _normalisiere_servernamen(servername)
        return any(_normalisiere_servernamen(zeile.servername) == suchwert for zeile in self._zeilen_nach_id.values())

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
        self.tree.set(item_id, spaltenname, _checkbox_wert(neuer_wert))

    def server_manuell_hinzufuegen(self) -> None:
        servername = self.entry_servername.get().strip()
        if not servername:
            messagebox.showwarning("Eingabe fehlt", "Bitte einen Servernamen eingeben.")
            return

        zeile = ServerTabellenZeile(
            servername=servername,
            sql=self.var_sql.get(),
            app=self.var_app.get(),
            ctx=self.var_ctx.get(),
            quelle="manuell",
            status="bereit",
        )
        self._fuege_zeile_ein(zeile)

    def discovery_starten(self) -> None:
        """Startet eine einfache Discovery und fügt neue Hosts dedupliziert ein."""
        basis = simpledialog.askstring(
            "Discovery",
            "IPv4-Basis eingeben (z. B. 192.168.178):",
            parent=self.master,
        )
        if not basis:
            return

        startwert = simpledialog.askinteger("Discovery", "Startbereich (z. B. 1):", parent=self.master)
        endwert = simpledialog.askinteger("Discovery", "Endbereich (z. B. 30):", parent=self.master)
        if startwert is None or endwert is None:
            return

        self._setze_status_alle("Discovery läuft")
        self.master.update_idletasks()

        try:
            hosts = entdecke_server_kandidaten(basis=basis.strip(), start=startwert, ende=endwert)
        except Exception as exc:  # noqa: BLE001 - robuste GUI-Fehlerbehandlung.
            logger.exception("Discovery fehlgeschlagen")
            messagebox.showerror("Discovery-Fehler", f"Discovery konnte nicht ausgeführt werden: {exc}")
            self._setze_status_alle("bereit")
            return

        hinzugefuegt = 0
        for host in hosts:
            vorher = len(self._zeilen_nach_id)
            self._fuege_zeile_ein(ServerTabellenZeile(servername=host, quelle="Discovery", status="bereit"))
            if len(self._zeilen_nach_id) > vorher:
                hinzugefuegt += 1

        messagebox.showinfo(
            "Discovery abgeschlossen",
            f"Gefundene Hosts: {len(hosts)}\nNeu übernommen: {hinzugefuegt}\nIgnorierte Duplikate: {len(hosts) - hinzugefuegt}",
        )
        self._setze_status_alle("bereit")

    def _setze_status_alle(self, status: str) -> None:
        for item_id, zeile in self._zeilen_nach_id.items():
            zeile.status = status
            self.tree.set(item_id, _SPALTE_STATUS, status)

    def eintrag_loeschen(self) -> None:
        auswahl = self.tree.selection()
        if not auswahl:
            return

        for item_id in auswahl:
            self._zeilen_nach_id.pop(item_id, None)
            self.tree.delete(item_id)

    def _zeige_ergebnisse_aufklappbar(self, ergebnisse: list[AnalyseErgebnis]) -> None:
        """Baut Kurzstatus + Detailansicht als aufklappbaren Ergebnisbaum auf."""
        for item_id in self.tree_ergebnisse.get_children(""):
            self.tree_ergebnisse.delete(item_id)

        for ergebnis in ergebnisse:
            server_knoten = self.tree_ergebnisse.insert(
                "",
                "end",
                text=ergebnis.server,
                values=(_kurzstatus(ergebnis),),
                open=False,
            )
            for detail in _detailzeilen(ergebnis):
                self.tree_ergebnisse.insert(server_knoten, "end", text="", values=(detail,))

    def analyse_starten(self) -> None:
        zeilen = list(self._zeilen_nach_id.values())
        ziele = _baue_serverziele(zeilen)
        if not ziele:
            messagebox.showwarning("Keine Server", "Bitte mindestens einen gültigen Server hinzufügen.")
            return

        zusammenfassung = _deklarationszusammenfassung(ziele, zeilen)
        bestaetigt = messagebox.askokcancel("Analyse bestätigen", zusammenfassung)
        if not bestaetigt:
            return

        self._setze_status_alle("Analyse läuft")
        self.master.update_idletasks()

        try:
            lauf_id = erstelle_lauf_id()
            setze_lauf_id(lauf_id)
            self._lauf_id_var.set(lauf_id)
            ergebnisse = analysiere_mehrere_server(ziele, lauf_id=lauf_id)
        except Exception as exc:  # noqa: BLE001 - GUI soll Fehler anzeigen statt abzubrechen.
            logger.exception("Mehrserveranalyse fehlgeschlagen")
            messagebox.showerror("Analysefehler", f"Mehrserveranalyse fehlgeschlagen: {exc}")
            self._setze_status_alle("fehlerhaft")
            return

        status_nach_server = {ergebnis.server.lower(): "analysiert" for ergebnis in ergebnisse}
        for item_id, zeile in self._zeilen_nach_id.items():
            zeile.status = status_nach_server.get(_normalisiere_servernamen(zeile.servername), "unbekannt")
            self.tree.set(item_id, _SPALTE_STATUS, zeile.status)

        self._zeige_ergebnisse_aufklappbar(ergebnisse)
        messagebox.showinfo("Analyse abgeschlossen", f"Analyse abgeschlossen. Lauf-ID: {self._lauf_id_var.get()}")


def start_gui() -> None:
    """Programmatischer Einstiegspunkt für die Mehrserver-GUI."""
    setze_lauf_id(erstelle_lauf_id())
    root = tk.Tk()
    MehrserverAnalyseGUI(root)
    root.mainloop()


def main() -> None:
    """CLI-kompatibler Startpunkt."""
    start_gui()


if __name__ == "__main__":
    main()
