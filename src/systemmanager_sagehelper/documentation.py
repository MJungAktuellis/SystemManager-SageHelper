"""Erzeugung strukturierter Markdown-Dokumentationen aus Analysezustand und Laufartefakten."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from .models import AnalyseErgebnis
from .logging_setup import konfiguriere_logger

logger = konfiguriere_logger(__name__, dateiname="doc_generator.log")

Berichtsmodus = Literal["voll", "kompakt"]


@dataclass(slots=True)
class DokumentKopf:
    """Beschreibt den Kopfbereich eines Berichts mit Laufmetadaten."""

    kunde: str = "nicht angegeben"
    umgebung: str = "nicht angegeben"
    lauf_id: str = "nicht gesetzt"
    zeitstempel: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class BefundKategorie:
    """Hält die Befunde einer einzelnen Kategorie als Bullet-Liste."""

    titel: str
    eintraege: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Massnahme:
    """Beschreibt eine priorisierte Maßnahme für offene Punkte."""

    prioritaet: str
    text: str


@dataclass(slots=True)
class ArtefaktVerweise:
    """Sammelt alle relevanten Laufartefakte für eine konsistente Verlinkung."""

    analysebericht: str | None = None
    log_pfade: list[str] = field(default_factory=list)
    lauf_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DokumentModell:
    """Strukturiertes Dokumentmodell als Single Source of Truth für die Markdown-Ausgabe."""

    kopf: DokumentKopf
    executive_summary: list[str]
    serveruebersicht: list[list[str]]
    befunde: list[BefundKategorie]
    massnahmen: list[Massnahme]
    artefakte: ArtefaktVerweise
    log_anhang: str | None = None


_PRIORITAET_SORTIERUNG = {"P1": 0, "P2": 1, "P3": 2}


def lese_logs(log_verzeichnis: str, *, include_altformate: bool = True) -> str:
    """Liest konsolidierte Logs aus ``*.log`` und optional aus Legacy-``*.txt``-Dateien."""
    logs_content: list[str] = []
    basis = Path(log_verzeichnis)
    muster = ["*.log"]
    if include_altformate:
        muster.append("*.txt")

    log_pfade: list[Path] = []
    for pattern in muster:
        log_pfade.extend(sorted(basis.glob(pattern)))

    for log_pfad in log_pfade:
        inhalt = log_pfad.read_text(encoding="utf-8")
        logs_content.append(f"# Log-Datei: {log_pfad.name}\n")
        logs_content.append(inhalt + "\n")

    logger.info("Alle Logs erfolgreich gelesen. Dateien: %s", [pfad.name for pfad in log_pfade])
    return "\n".join(logs_content)


def generiere_markdown_bericht(inhalt: str, output_pfad: str | Path) -> None:
    """Erstellt eine Markdown-Datei basierend auf gegebenem Inhalt."""
    Path(output_pfad).write_text(inhalt, encoding="utf-8")
    logger.info("Markdown-Bericht erfolgreich erstellt: %s", output_pfad)


def _render_tabelle(ueberschriften: list[str], zeilen: list[list[str]]) -> list[str]:
    """Rendert eine einfache Markdown-Tabelle."""
    if not zeilen:
        return ["| Hinweis |", "| --- |", "| Keine Daten vorhanden |"]
    return [
        "| " + " | ".join(ueberschriften) + " |",
        "| " + " | ".join("---" for _ in ueberschriften) + " |",
        *["| " + " | ".join(zeile) + " |" for zeile in zeilen],
    ]


def _ermittle_lauf_id(ergebnisse: list[AnalyseErgebnis]) -> str:
    """Liest die Lauf-ID aus den Analyseergebnissen."""
    for ergebnis in ergebnisse:
        if ergebnis.lauf_id:
            return ergebnis.lauf_id
    return "nicht gesetzt"


def _baue_executive_summary(ergebnisse: list[AnalyseErgebnis]) -> list[str]:
    """Erzeugt eine managementtaugliche Summary mit Schlüsselkennzahlen."""
    gesamt = len(ergebnisse)
    warnungen = 0
    blockierte_ports = 0

    for ergebnis in ergebnisse:
        blockiert = sum(1 for port in ergebnis.ports if not port.offen)
        if blockiert or ergebnis.hinweise:
            warnungen += 1
        blockierte_ports += blockiert

    return [
        f"Analysierte Server: {gesamt}",
        f"Server mit offenen Punkten: {warnungen}",
        f"Blockierte/unerreichbare Ports gesamt: {blockierte_ports}",
    ]


def _baue_serveruebersicht(ergebnisse: list[AnalyseErgebnis]) -> list[list[str]]:
    """Erzeugt die tabellarische Serverübersicht für den Bericht."""
    zeilen: list[list[str]] = []
    for ergebnis in ergebnisse:
        blockiert = sum(1 for port in ergebnis.ports if not port.offen)
        zeilen.append(
            [
                ergebnis.server,
                ", ".join(ergebnis.rollen) if ergebnis.rollen else "nicht gesetzt",
                ergebnis.betriebssystem or "unbekannt",
                ergebnis.sage_version or "nicht erkannt",
                str(blockiert),
            ]
        )
    return zeilen


def _baue_befund_kategorien(ergebnisse: list[AnalyseErgebnis]) -> list[BefundKategorie]:
    """Verdichtet Analyseobjekte in kategorisierte Befunde statt Rohlog-Ausgabe."""
    rollen: list[str] = []
    ports: list[str] = []
    freigaben: list[str] = []
    hinweise: list[str] = []

    for ergebnis in ergebnisse:
        rollen.append(
            f"{ergebnis.server}: {', '.join(ergebnis.rollen) if ergebnis.rollen else 'keine Rolle erkannt'} "
            f"(Quelle: {ergebnis.rollenquelle or 'unbekannt'})"
        )

        offene = [str(port.port) for port in ergebnis.ports if port.offen]
        blockierte = [str(port.port) for port in ergebnis.ports if not port.offen]
        ports.append(
            f"{ergebnis.server}: offen [{', '.join(offene) or '-'}], blockiert [{', '.join(blockierte) or '-'}]"
        )

        freigabe_hinweise = [eintrag for eintrag in ergebnis.hinweise if "freig" in eintrag.lower()]
        if freigabe_hinweise:
            freigaben.extend(f"{ergebnis.server}: {eintrag}" for eintrag in freigabe_hinweise)

        sonstige_hinweise = [eintrag for eintrag in ergebnis.hinweise if "freig" not in eintrag.lower()]
        hinweise.extend(f"{ergebnis.server}: {eintrag}" for eintrag in sonstige_hinweise)

    return [
        BefundKategorie("Rollen", rollen),
        BefundKategorie("Ports", ports),
        BefundKategorie("Freigaben", freigaben or ["Keine spezifischen Freigabehinweise vorhanden"]),
        BefundKategorie("Hinweise", hinweise or ["Keine zusätzlichen Hinweise vorhanden"]),
    ]


def _baue_massnahmen(ergebnisse: list[AnalyseErgebnis]) -> list[Massnahme]:
    """Leitet priorisierte Maßnahmen direkt aus dem Analysezustand ab."""
    massnahmen: list[Massnahme] = []
    for ergebnis in ergebnisse:
        for port in ergebnis.ports:
            if not port.offen:
                massnahmen.append(
                    Massnahme(
                        prioritaet="P1",
                        text=f"{ergebnis.server}: Port {port.port} ({port.bezeichnung}) prüfen/freischalten",
                    )
                )
        for hinweis in ergebnis.hinweise:
            prioritaet = "P2" if "nicht aktiv" in hinweis.lower() else "P3"
            massnahmen.append(Massnahme(prioritaet=prioritaet, text=f"{ergebnis.server}: {hinweis}"))

    if not massnahmen:
        return [Massnahme(prioritaet="P3", text="Keine offenen Maßnahmen erkannt")]

    return sorted(massnahmen, key=lambda eintrag: (_PRIORITAET_SORTIERUNG.get(eintrag.prioritaet, 99), eintrag.text))


def _baue_artefakt_verweise(
    ergebnisse: list[AnalyseErgebnis],
    *,
    analysebericht_pfad: str | None,
    log_verzeichnis: str,
) -> ArtefaktVerweise:
    """Erzeugt konsistente Artefaktverweise inkl. Lauf-ID-Korrelation."""
    logs = sorted(str(pfad) for pfad in Path(log_verzeichnis).glob("*.log"))
    lauf_ids = sorted({eintrag.lauf_id for eintrag in ergebnisse if eintrag.lauf_id})
    return ArtefaktVerweise(
        analysebericht=analysebericht_pfad,
        log_pfade=logs,
        lauf_ids=lauf_ids,
    )


def _baue_dokumentmodell(
    ergebnisse: list[AnalyseErgebnis],
    *,
    kunde: str,
    umgebung: str,
    analysebericht_pfad: str | None,
    log_verzeichnis: str,
    log_anhang: str | None,
) -> DokumentModell:
    """Baut das vollständige Dokumentmodell aus dem Analyse-State."""
    return DokumentModell(
        kopf=DokumentKopf(kunde=kunde, umgebung=umgebung, lauf_id=_ermittle_lauf_id(ergebnisse)),
        executive_summary=_baue_executive_summary(ergebnisse),
        serveruebersicht=_baue_serveruebersicht(ergebnisse),
        befunde=_baue_befund_kategorien(ergebnisse),
        massnahmen=_baue_massnahmen(ergebnisse),
        artefakte=_baue_artefakt_verweise(
            ergebnisse,
            analysebericht_pfad=analysebericht_pfad,
            log_verzeichnis=log_verzeichnis,
        ),
        log_anhang=log_anhang,
    )


def _render_dokumentmodell(modell: DokumentModell, *, berichtsmodus: Berichtsmodus) -> str:
    """Rendert das strukturierte Dokumentmodell als Markdown."""
    ist_kompakt_modus = berichtsmodus == "kompakt"
    zeilen: list[str] = [
        "# ServerDokumentation",
        "",
        "## Kopfbereich",
        f"- Kunde: {modell.kopf.kunde}",
        f"- Umgebung: {modell.kopf.umgebung}",
        f"- Lauf-ID: {modell.kopf.lauf_id}",
        f"- Zeit: {modell.kopf.zeitstempel.isoformat(timespec='seconds')}",
        f"- Berichtsmodus: {'Kompaktbericht' if ist_kompakt_modus else 'Vollbericht'}",
        "",
        "## Zusammenfassung",
        *[f"- {eintrag}" for eintrag in modell.executive_summary],
        "",
        "## Serverübersicht",
        *_render_tabelle(
            ["Server", "Rollen", "Betriebssystem", "Sage-Version", "Blockierte Ports"],
            modell.serveruebersicht,
        ),
        "",
    ]

    if not ist_kompakt_modus:
        zeilen.extend(["## Zielgruppe: Admin", "", "### Befunde", ""])
        for kategorie in modell.befunde:
            zeilen.append(f"#### {kategorie.titel}")
            zeilen.extend(f"- {eintrag}" for eintrag in kategorie.eintraege)
            zeilen.append("")
    else:
        zeilen.extend(
            [
                "## Zielgruppe: Drittuser",
                "- Fokus auf offene Risiken und priorisierte Maßnahmen.",
                "- Technische Detailwerte und Rohlogs siehe Artefaktverweise/Anhang.",
                "",
            ]
        )

    zeilen.extend(["## Zielgruppe: Support", "- Priorisierte Maßnahmen für Betrieb und Entstörung.", ""])

    zeilen.extend(["## Maßnahmen", "| Priorität | Maßnahme |", "| --- | --- |"])
    zeilen.extend(f"| {eintrag.prioritaet} | {eintrag.text} |" for eintrag in modell.massnahmen)

    zeilen.extend(["", "## Artefakte"])
    zeilen.append(f"- Analysebericht: {modell.artefakte.analysebericht or 'nicht gesetzt'}")
    if modell.artefakte.lauf_ids:
        zeilen.append(f"- Lauf-IDs: {', '.join(modell.artefakte.lauf_ids)}")
    else:
        zeilen.append("- Lauf-IDs: keine")

    if modell.artefakte.log_pfade:
        zeilen.append("- Logpfade:")
        zeilen.extend(f"  - {pfad}" for pfad in modell.artefakte.log_pfade)
    else:
        zeilen.append("- Logpfade: keine")

    if modell.log_anhang:
        zeilen.extend(["", "## Log-Anhang (Referenz)", modell.log_anhang])

    return "\n".join(zeilen).strip() + "\n"


def erstelle_dokumentation(
    log_verzeichnis: str,
    output_verzeichnis: str,
    *,
    analyse_ergebnisse: list[AnalyseErgebnis] | None = None,
    kunde: str = "nicht angegeben",
    umgebung: str = "nicht angegeben",
    berichtsmodus: Berichtsmodus = "voll",
    analysebericht_pfad: str | None = None,
    logs_als_anhang: bool = True,
) -> Path:
    """Erstellt eine strukturierte Dokumentation aus Analyse-State mit optionalem Log-Anhang.

    Logs werden bewusst nur als Referenz verwendet. Die eigentlichen Inhaltsblöcke
    basieren auf ``AnalyseErgebnis``-Objekten, um reproduzierbare und filterbare
    Reports für Technik und Management zu erzeugen.
    """
    logger.info("Starte Dokumentationserstellung im Modus '%s'...", berichtsmodus)
    ziel = Path(output_verzeichnis)
    ziel.mkdir(parents=True, exist_ok=True)

    log_anhang = lese_logs(log_verzeichnis, include_altformate=True) if logs_als_anhang else None
    modell = _baue_dokumentmodell(
        analyse_ergebnisse or [],
        kunde=kunde,
        umgebung=umgebung,
        analysebericht_pfad=analysebericht_pfad,
        log_verzeichnis=log_verzeichnis,
        log_anhang=log_anhang,
    )

    markdown_datei = ziel / "ServerDokumentation.md"
    generiere_markdown_bericht(_render_dokumentmodell(modell, berichtsmodus=berichtsmodus), markdown_datei)
    logger.info("Dokumentationserstellung abgeschlossen.")
    return markdown_datei
