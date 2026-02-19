"""Grafischer Installations-Wizard für SystemManager-SageHelper.

Das Modul bietet einen mehrstufigen Tkinter-Workflow und nutzt die gleiche
Installer-Kernlogik wie die CLI, ohne Benutzereingaben via ``input()``.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Literal

from systemmanager_sagehelper.gui_shell import GuiShell
from systemmanager_sagehelper.gui_state import GUIStateStore, erstelle_installer_modulzustand
from systemmanager_sagehelper.installation_state import _ermittle_app_version, schreibe_installations_marker
from systemmanager_sagehelper.installer import (
    ErgebnisStatus,
    InstallationsErgebnis,
    InstallationsFehler,
    InstallationsKomponente,
    STANDARD_REIHENFOLGE,
    erstelle_desktop_verknuepfung_fuer_python_installation,
    erstelle_standard_komponenten,
    konfiguriere_logging,
    schreibe_installationsreport,
    validiere_auswahl_und_abhaengigkeiten,
)
from systemmanager_sagehelper.installer_options import (
    InstallerOptionen,
    baue_inno_setup_parameter,
    mappe_inno_tasks,
)
from systemmanager_sagehelper.logging_setup import erstelle_lauf_id


LOGGER = logging.getLogger(__name__)

WizardModus = Literal["install", "maintenance"]


@dataclass(slots=True)
class WizardSchritt:
    """Beschreibt einen einzelnen Wizard-Schritt inklusive Titel."""

    id: str
    titel: str


class InstallerWizardGUI:
    """Mehrstufiger Installer mit konsistenter Shell-Optik für das Haupttool."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        mode: WizardModus = "install",
        repo_root: Path | None = None,
        on_finished: Callable[[bool], None] | None = None,
    ) -> None:
        self.mode = mode
        self.repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
        self.on_finished = on_finished
        self.state_store = GUIStateStore()

        if isinstance(master, tk.Tk):
            self.window = master
            self._eigenes_root = True
        else:
            self.window = tk.Toplevel(master)
            self.window.transient(master)
            self.window.grab_set()
            self._eigenes_root = False

        self.window.geometry("980x780")
        self.window.minsize(900, 700)

        self.shell = GuiShell(
            self.window,
            titel=self._wizard_titel,
            untertitel=self._wizard_untertitel,
            on_save=self._speichere_optionen,
            on_back=self._zurueck,
            on_exit=self._beenden,
        )

        self.lauf_id = erstelle_lauf_id()
        self.shell.setze_lauf_id(self.lauf_id)

        self.schritte = [
            WizardSchritt("willkommen", "Willkommen"),
            WizardSchritt("pfad_optionen", "Installationspfad / Optionen"),
            WizardSchritt("komponenten", "Komponenten"),
            WizardSchritt("fortschritt", "Fortschritt"),
            WizardSchritt("abschluss", "Abschluss"),
        ]
        self.aktiver_schritt = 0

        self.installationspfad_var = tk.StringVar(value=str(self.repo_root))
        self.option_marker_var = tk.BooleanVar(value=True)
        self.option_report_var = tk.BooleanVar(value=True)
        # One-Click-Installationen sollen standardmäßig eine Desktop-Verknüpfung anlegen.
        self.option_desktop_icon_var = tk.BooleanVar(value=True)
        self.statustext_var = tk.StringVar(value=f"Noch kein {self._vorgang_nomen.lower()} gestartet.")

        self.log_datei: Path | None = None
        self.report_datei: Path | None = None
        self.marker_datei: Path | None = None
        self.installationsfehler: str | None = None
        self.desktop_icon_fehler: str | None = None
        self.desktop_icon_pfad: Path | None = None
        self.installation_laueft = False

        self.komponenten = erstelle_standard_komponenten(self.repo_root)
        self.komponenten_vars = {
            komponenten_id: tk.BooleanVar(value=self.komponenten[komponenten_id].default_aktiv)
            for komponenten_id in STANDARD_REIHENFOLGE
            if komponenten_id in self.komponenten
        }

        self.inhalt = ttk.Frame(self.shell.content_frame)
        self.inhalt.pack(fill="both", expand=True)

        self.navigation = ttk.Frame(self.shell.content_frame)
        self.navigation.pack(fill="x", pady=(8, 0))

        self.btn_zurueck = ttk.Button(self.navigation, text="← Zurück", command=self._zurueck)
        self.btn_zurueck.pack(side="left")
        self.btn_weiter = ttk.Button(self.navigation, text="Weiter →", style="Primary.TButton", command=self._weiter)
        self.btn_weiter.pack(side="right")

        self.window.protocol("WM_DELETE_WINDOW", self._beenden)
        self._render_schritt()

    @property
    def _ist_wartungsmodus(self) -> bool:
        return self.mode == "maintenance"

    @property
    def _wizard_titel(self) -> str:
        return "Wartungsassistent" if self._ist_wartungsmodus else "Installationsassistent"

    @property
    def _wizard_untertitel(self) -> str:
        if self._ist_wartungsmodus:
            return "Integrität prüfen, Komponentenstatus bewerten und gezielt reparieren"
        return "Schrittweise Installation für SystemManager-SageHelper"

    @property
    def _vorgang_nomen(self) -> str:
        return "Wartung" if self._ist_wartungsmodus else "Installation"

    @property
    def _vorgang_verb(self) -> str:
        return "Wartung" if self._ist_wartungsmodus else "Installation"

    def _beenden(self) -> None:
        """Schließt das Wizard-Fenster geordnet."""
        if self.installation_laueft:
            messagebox.showwarning(
                f"{self._vorgang_nomen} aktiv",
                f"Bitte warten Sie, bis die {self._vorgang_nomen.lower()} abgeschlossen ist.",
                parent=self.window,
            )
            return
        self.window.destroy()

    def _speichere_optionen(self) -> None:
        """Persistiert keine Dateien, sondern bestätigt die aktuelle Wizard-Konfiguration."""
        self.shell.setze_status("Wizard-Optionen übernommen")
        self.shell.logge_meldung(
            f"Optionen übernommen ({self.mode}): Pfad={self.installationspfad_var.get()} | "
            f"Marker={self.option_marker_var.get()} | Report={self.option_report_var.get()} | "
            f"DesktopIcon={self.option_desktop_icon_var.get()}"
        )

    def _render_schritt(self) -> None:
        for child in self.inhalt.winfo_children():
            child.destroy()

        schritt = self.schritte[self.aktiver_schritt]
        self.shell.setze_status(f"Schritt {self.aktiver_schritt + 1}/{len(self.schritte)}: {schritt.titel}")

        renderer = {
            "willkommen": self._render_willkommen,
            "pfad_optionen": self._render_pfad_optionen,
            "komponenten": self._render_komponenten,
            "fortschritt": self._render_fortschritt,
            "abschluss": self._render_abschluss,
        }[schritt.id]
        renderer()
        self._aktualisiere_navigation()

    def _aktualisiere_navigation(self) -> None:
        letzter = len(self.schritte) - 1
        self.btn_zurueck.config(state="normal" if self.aktiver_schritt > 0 else "disabled")

        if self.aktiver_schritt < 2:
            self.btn_weiter.config(state="normal", text="Weiter →", command=self._weiter)
        elif self.aktiver_schritt == 2:
            self.btn_weiter.config(state="normal", text=f"{self._vorgang_nomen} starten", command=self._starte_installation)
        elif self.aktiver_schritt == 3:
            self.btn_weiter.config(state="disabled" if self.installation_laueft else "normal", text="Weiter →", command=self._weiter)
        else:
            self.btn_weiter.config(text="Schließen", state="normal", command=self._beenden)

        if self.aktiver_schritt == letzter:
            self.btn_zurueck.config(state="disabled")

    def _weiter(self) -> None:
        if self.aktiver_schritt >= len(self.schritte) - 1:
            return
        if self.aktiver_schritt == 1 and not self._pruefe_installationspfad():
            return
        self.aktiver_schritt += 1
        self._render_schritt()

    def _zurueck(self) -> None:
        if self.installation_laueft:
            return
        if self.aktiver_schritt <= 0:
            return
        self.aktiver_schritt -= 1
        self._render_schritt()

    def _render_willkommen(self) -> None:
        rahmen = ttk.LabelFrame(self.inhalt, text="Willkommen", style="Section.TLabelframe")
        rahmen.pack(fill="both", expand=True)
        text = (
            f"Dieser Assistent führt Sie durch die {self._vorgang_nomen.lower()} von SystemManager-SageHelper.\n\n"
            "Ablauf:\n"
            "1) Installationspfad und Optionen prüfen\n"
            "2) Komponenten auswählen bzw. prüfen\n"
            f"3) {self._vorgang_nomen} ausführen\n"
            "4) Ergebnisse prüfen"
        )
        if self._ist_wartungsmodus:
            text += (
                "\n\nIm Wartungsmodus werden keine Vollinstallationsaktionen angeboten. "
                "Stattdessen stehen Integritätsprüfung, Versions-/Komponentencheck und "
                "gezielte Reparatur/Aktualisierung bereit."
            )
        ttk.Label(rahmen, text=text, justify="left").pack(anchor="w", padx=10, pady=10)

    def _render_pfad_optionen(self) -> None:
        rahmen = ttk.LabelFrame(self.inhalt, text="Installationspfad / Optionen", style="Section.TLabelframe")
        rahmen.pack(fill="both", expand=True)

        pfad_zeile = ttk.Frame(rahmen)
        pfad_zeile.pack(fill="x", padx=10, pady=(12, 8))
        ttk.Label(pfad_zeile, text="Repository-/Installationspfad:").pack(anchor="w")
        ttk.Entry(pfad_zeile, textvariable=self.installationspfad_var).pack(fill="x", side="left", expand=True, pady=(6, 0))
        ttk.Button(pfad_zeile, text="Durchsuchen", command=self._waehle_installationspfad).pack(side="left", padx=(8, 0), pady=(6, 0))

        optionen = ttk.Frame(rahmen)
        optionen.pack(fill="x", padx=10, pady=8)
        ttk.Checkbutton(optionen, text="Installationsreport schreiben", variable=self.option_report_var).pack(anchor="w")
        ttk.Checkbutton(optionen, text="Installationsmarker aktualisieren", variable=self.option_marker_var).pack(anchor="w")
        if self._ist_wartungsmodus:
            # Im Wartungsmodus wird keine Vollinstallation angestoßen, daher sind
            # One-Click-Artefakte wie ein neues Desktop-Icon hier bewusst ausgeblendet.
            self.option_desktop_icon_var.set(False)
            ttk.Label(
                optionen,
                text="Desktop-Verknüpfung ist im Wartungsmodus deaktiviert.",
                style="Muted.TLabel",
                wraplength=840,
            ).pack(anchor="w", pady=(2, 0))
        else:
            ttk.Checkbutton(
                optionen,
                text="Desktop-Verknüpfung erstellen (empfohlen)",
                variable=self.option_desktop_icon_var,
            ).pack(anchor="w")
            ttk.Label(
                optionen,
                text="Standard für One-Click: aktiv. Im Abschluss wird der Status separat ausgewiesen.",
                style="Muted.TLabel",
                wraplength=840,
            ).pack(anchor="w", pady=(2, 0))

        info = (
            "Hinweis: Der Pfad muss eine gültige Projektstruktur enthalten, "
            "damit Komponenten wie requirements.txt und Launcher-Dateien korrekt verarbeitet werden."
        )
        ttk.Label(rahmen, text=info, wraplength=850).pack(anchor="w", padx=10, pady=(12, 0))

    def _render_komponenten(self) -> None:
        rahmen = ttk.LabelFrame(self.inhalt, text="Komponenten", style="Section.TLabelframe")
        rahmen.pack(fill="both", expand=True)

        ttk.Label(
            rahmen,
            text=(
                "Wählen Sie die Komponenten für die Ausführung. "
                "Im Wartungsmodus entspricht dies einer gezielten Reparatur/Aktualisierung."
                if self._ist_wartungsmodus
                else "Wählen Sie die Installationskomponenten. Abhängigkeiten werden automatisch validiert."
            ),
            wraplength=860,
        ).pack(anchor="w", padx=10, pady=(10, 8))

        for komponenten_id in STANDARD_REIHENFOLGE:
            if komponenten_id not in self.komponenten_vars:
                continue
            komponente = self.komponenten[komponenten_id]
            ttk.Checkbutton(
                rahmen,
                text=f"{komponente.name} ({komponente.id})",
                variable=self.komponenten_vars[komponenten_id],
            ).pack(anchor="w", padx=16, pady=4)

    def _render_fortschritt(self) -> None:
        rahmen = ttk.LabelFrame(self.inhalt, text="Fortschritt", style="Section.TLabelframe")
        rahmen.pack(fill="both", expand=True)

        ttk.Label(rahmen, textvariable=self.statustext_var).pack(anchor="w", padx=10, pady=(10, 8))
        self.progress = ttk.Progressbar(rahmen, mode="indeterminate")
        self.progress.pack(fill="x", padx=10)

        self.fortschritt_log = tk.Text(rahmen, height=18, state="disabled")
        self.fortschritt_log.pack(fill="both", expand=True, padx=10, pady=10)

        if self.installation_laueft:
            self.progress.start(10)

    def _render_abschluss(self) -> None:
        rahmen = ttk.LabelFrame(self.inhalt, text="Abschluss", style="Section.TLabelframe")
        rahmen.pack(fill="both", expand=True)

        status = (
            f"{self._vorgang_nomen} erfolgreich abgeschlossen."
            if not self.installationsfehler
            else f"{self._vorgang_nomen} fehlgeschlagen."
        )
        ttk.Label(rahmen, text=status).pack(anchor="w", padx=10, pady=(12, 8))

        details: list[str] = []
        if self.log_datei:
            details.append(f"Logdatei: {self.log_datei}")
        if self.report_datei:
            details.append(f"Installationsreport: {self.report_datei}")
        if self.marker_datei:
            details.append(f"Installationsmarker: {self.marker_datei}")
        if self.desktop_icon_pfad:
            details.append(f"Desktop-Verknüpfung: {self.desktop_icon_pfad}")
        if self.desktop_icon_fehler:
            details.append(f"Desktop-Verknüpfung Fehler: {self.desktop_icon_fehler}")
        if self.installationsfehler:
            details.append(f"Fehler: {self.installationsfehler}")

        ttk.Label(rahmen, text="\n".join(details) or "Keine Detaildaten verfügbar.", justify="left").pack(
            anchor="w", padx=10, pady=(0, 10)
        )

    def _waehle_installationspfad(self) -> None:
        ausgewaehlt = filedialog.askdirectory(parent=self.window)
        if ausgewaehlt:
            self.installationspfad_var.set(ausgewaehlt)

    def _pruefe_installationspfad(self) -> bool:
        pfad = Path(self.installationspfad_var.get()).expanduser().resolve()
        erwartete_datei = pfad / "src" / "systemmanager_sagehelper" / "installer.py"
        if erwartete_datei.exists():
            return True

        messagebox.showerror(
            "Ungültiger Installationspfad",
            "Der gewählte Pfad enthält keine gültige Projektstruktur.",
            parent=self.window,
        )
        return False

    def _starte_installation(self) -> None:
        if self.installation_laueft:
            return
        if not self._pruefe_installationspfad():
            return

        self.installation_laueft = True
        self.installationsfehler = None
        self.desktop_icon_fehler = None
        self.desktop_icon_pfad = None
        self.report_datei = None
        self.marker_datei = None
        self.statustext_var.set(f"{self._vorgang_nomen} läuft …")

        self.aktiver_schritt = 3
        self._render_schritt()
        self.progress.start(10)

        worker = threading.Thread(target=self._fuehre_installation_hintergrund_aus, daemon=True)
        worker.start()

    def _fuege_fortschrittslog_hinzu(self, text: str) -> None:
        self.shell.logge_meldung(text)
        if not hasattr(self, "fortschritt_log"):
            return
        self.fortschritt_log.config(state="normal")
        self.fortschritt_log.insert(tk.END, text + "\n")
        self.fortschritt_log.config(state="disabled")
        self.fortschritt_log.see(tk.END)

    def _fuehre_installation_hintergrund_aus(self) -> None:
        try:
            ziel_root = Path(self.installationspfad_var.get()).expanduser().resolve()
            self.log_datei = konfiguriere_logging(ziel_root)
            self.komponenten = erstelle_standard_komponenten(ziel_root)
            auswahl = {komp_id: var.get() for komp_id, var in self.komponenten_vars.items()}

            ergebnisse = self._fuehre_komponenten_mit_fortschritt_aus(self.komponenten, auswahl)
            if self._ist_wartungsmodus:
                self.window.after(0, self._fuege_fortschrittslog_hinzu, "Integritätsprüfung abgeschlossen.")
                self.window.after(0, self._fuege_fortschrittslog_hinzu, "Versions-/Komponentencheck abgeschlossen.")
            desktop_verknuepfung_status = "Desktop-Verknüpfung: Deaktiviert"

            if self.option_marker_var.get():
                self.marker_datei = schreibe_installations_marker(repo_root=ziel_root)

            # Persistiert den Installer-Zustand zentral, damit Dashboard und weitere GUI-Module
            # den Erfolg unabhängig vom aktuellen Fenster reproduzierbar auslesen können.
            installer_status = erstelle_installer_modulzustand(
                installiert=True,
                version=_ermittle_app_version(),
                bericht_pfad=str(self.report_datei) if self.report_datei else "",
            )
            installer_status["letzte_aktion"] = self.mode
            self.state_store.speichere_modulzustand("installer", installer_status)

            installer_optionen = InstallerOptionen(desktop_icon=self.option_desktop_icon_var.get())
            inno_tasks = mappe_inno_tasks(installer_optionen)
            inno_parameter = baue_inno_setup_parameter(installer_optionen)
            self.window.after(0, self._fuege_fortschrittslog_hinzu, f"Inno-Tasks aus Optionen: {inno_tasks or 'keine'}")
            self.window.after(0, self._fuege_fortschrittslog_hinzu, f"Inno-Parameter: {' '.join(inno_parameter)}")

            if installer_optionen.desktop_icon and not self._ist_wartungsmodus:
                try:
                    self.desktop_icon_pfad = erstelle_desktop_verknuepfung_fuer_python_installation(ziel_root)
                    desktop_verknuepfung_status = f"Desktop-Verknüpfung: Erfolgreich erstellt ({self.desktop_icon_pfad})"
                    LOGGER.info("Desktop-Verknüpfung erfolgreich erstellt: %s", self.desktop_icon_pfad)
                    self.window.after(
                        0,
                        self._fuege_fortschrittslog_hinzu,
                        f"Desktop-Verknüpfung erstellt: {self.desktop_icon_pfad}",
                    )
                except InstallationsFehler as exc:
                    self.desktop_icon_fehler = str(exc)
                    desktop_verknuepfung_status = f"Desktop-Verknüpfung: Fehler ({self.desktop_icon_fehler})"
                    LOGGER.warning("Desktop-Verknüpfung nicht erstellt: %s", self.desktop_icon_fehler)
                    self.window.after(
                        0,
                        self._fuege_fortschrittslog_hinzu,
                        f"[WARN] Desktop-Verknüpfung nicht erstellt: {self.desktop_icon_fehler}",
                    )
            else:
                LOGGER.info("Desktop-Verknüpfung wurde im GUI-Wizard deaktiviert.")

            if self.option_report_var.get():
                self.report_datei = schreibe_installationsreport(
                    ziel_root,
                    ergebnisse,
                    auswahl,
                    desktop_verknuepfung_status=desktop_verknuepfung_status,
                    einstiegspfad="gui",
                    optionen={
                        "Modus": "Wartung" if self._ist_wartungsmodus else "Installation",
                        "Installationsmarker": "aktiv" if self.option_marker_var.get() else "deaktiviert",
                        "Installationsreport": "aktiv" if self.option_report_var.get() else "deaktiviert",
                        "Desktop-Icon": "aktiv" if self.option_desktop_icon_var.get() else "deaktiviert",
                    },
                )

            self.window.after(0, self._installation_erfolgreich_abschliessen)
        except InstallationsFehler as exc:
            self.installationsfehler = str(exc)
            self.window.after(0, self._installation_mit_fehler_abschliessen)
        except Exception as exc:  # noqa: BLE001
            self.installationsfehler = f"Unerwarteter Fehler: {exc}"
            self.window.after(0, self._installation_mit_fehler_abschliessen)

    def _fuehre_komponenten_mit_fortschritt_aus(
        self,
        komponenten: dict[str, InstallationsKomponente],
        auswahl: dict[str, bool],
    ) -> list[InstallationsErgebnis]:
        """Führt Komponenten sequenziell aus und meldet Status in das GUI-Log."""
        validiere_auswahl_und_abhaengigkeiten(komponenten, auswahl)
        ergebnisse: list[InstallationsErgebnis] = []

        for komponenten_id in STANDARD_REIHENFOLGE:
            if not auswahl.get(komponenten_id, False):
                continue
            komponente = komponenten[komponenten_id]
            if self._ist_wartungsmodus:
                self.window.after(0, self._fuege_fortschrittslog_hinzu, f"Integritätsprüfung: {komponente.name}")
            self.window.after(0, self._fuege_fortschrittslog_hinzu, f"Starte: {komponente.name}")
            install_nachricht = komponente.install_fn()
            erfolgreich, verify_nachricht = komponente.verify_fn()
            if not erfolgreich:
                raise InstallationsFehler(
                    f"Verifikation fehlgeschlagen für '{komponente.name}': {verify_nachricht}"
                )
            gesamt_nachricht = f"{install_nachricht} | Verifikation: {verify_nachricht}"
            ergebnisse.append(
                InstallationsErgebnis(
                    komponenten_id=komponente.id,
                    name=komponente.name,
                    erfolgreich=True,
                    nachricht=gesamt_nachricht,
                    status=ErgebnisStatus.OK.value,
                    naechste_aktion="Keine Aktion erforderlich.",
                )
            )
            self.window.after(0, self._fuege_fortschrittslog_hinzu, f"Versions-/Komponentencheck: {verify_nachricht}")
            self.window.after(0, self._fuege_fortschrittslog_hinzu, f"Abgeschlossen: {komponente.name}")

        return ergebnisse

    def _installation_erfolgreich_abschliessen(self) -> None:
        self.installation_laueft = False
        if hasattr(self, "progress"):
            self.progress.stop()
        self.statustext_var.set(f"{self._vorgang_nomen} erfolgreich abgeschlossen.")
        self.shell.setze_status(f"{self._vorgang_nomen} abgeschlossen")
        self.aktiver_schritt = 4
        self._render_schritt()
        if self.on_finished:
            self.on_finished(True)

    def _installation_mit_fehler_abschliessen(self) -> None:
        self.installation_laueft = False
        if hasattr(self, "progress"):
            self.progress.stop()
        self.statustext_var.set(f"{self._vorgang_nomen} fehlgeschlagen.")
        self.shell.setze_status(f"{self._vorgang_nomen} fehlgeschlagen")
        if self.installationsfehler:
            self.shell.logge_meldung(f"[ERROR] {self.installationsfehler}")
        self.aktiver_schritt = 4
        self._render_schritt()
        if self.on_finished:
            self.on_finished(False)


def starte_installer_wizard(master: tk.Misc | None = None, mode: WizardModus = "install") -> InstallerWizardGUI:
    """Komfortfunktion zum Starten des Installers als eigenes Fenster oder Child."""
    if master is None:
        root = tk.Tk()
        wizard = InstallerWizardGUI(root, mode=mode)
        root.mainloop()
        return wizard

    return InstallerWizardGUI(master, mode=mode)


if __name__ == "__main__":
    starte_installer_wizard()
