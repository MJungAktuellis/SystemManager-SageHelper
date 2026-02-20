"""Kommandozeilen-Einstieg für Analyse, Strukturcheck und orchestrierten Gesamtablauf."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import (
    DiscoveryKonfiguration,
    DiscoveryRangeSegment,
    analysiere_mehrere_server,
    entdecke_server_kandidaten,
    entdecke_server_mehrere_ranges,
    entdecke_server_via_seeds,
)
from .confirmation import bestaetige_aenderungen_cli
from .folder_structure import ermittle_fehlende_ordner, lege_ordner_an
from .logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from .report import render_markdown
from .targeting import baue_serverziele, parse_deklarationen, parse_liste
from .share_policy import SharePolicy
from .workflow import WorkflowSchritt, fuehre_standard_workflow_aus

logger = konfiguriere_logger(__name__, dateiname="cli.log")


# Rückwärtskompatible Exporte für bestehende Tests/Integrationen.
_parse_liste = parse_liste
_parse_deklarationen = parse_deklarationen


def baue_parser() -> argparse.ArgumentParser:
    """Erstellt den CLI-Parser mit klaren Unterbefehlen."""
    parser = argparse.ArgumentParser(
        prog="sage-helper",
        description="Serveranalyse für Sage-Umgebungen",
    )
    sub = parser.add_subparsers(dest="kommando", required=True)

    scan = sub.add_parser("scan", help="Server analysieren und Markdown erzeugen")
    scan.add_argument("--server", default="", help="Kommagetrennte Serverliste, z. B. srv1,srv2")
    scan.add_argument("--rollen", default="APP", help="Standardrollen, z. B. SQL,APP,CTX")
    scan.add_argument(
        "--deklaration",
        default="",
        help="Rollendeklaration je Server, z. B. 'srv1=SQL,APP;srv2=CTX'",
    )
    scan.add_argument("--discover-base", default="", help="IPv4-Basis für Discovery, z. B. 192.168.10")
    scan.add_argument("--discover-start", type=int, default=1, help="Start-Hostnummer für Discovery")
    scan.add_argument("--discover-end", type=int, default=20, help="End-Hostnummer für Discovery")
    scan.add_argument(
        "--discover-range",
        action="append",
        default=[],
        help="Mehrere Discovery-Ranges im Format 192.168.10.1-30 (mehrfach erlaubt)",
    )
    scan.add_argument(
        "--discover-seed",
        action="append",
        default=[],
        help="Optionale Seed-Hosts für Discovery (mehrfach erlaubt)",
    )
    scan.add_argument(
        "--discover-seeds-from-ad-dns",
        action="store_true",
        help="Erweitert Seeds optional um DNS-SRV/AD-Computerobjekte (wenn verfügbar)",
    )
    scan.add_argument("--out", default="dokumentation.md", help="Zieldatei für Markdown-Export")

    workflow = sub.add_parser("workflow", help="Standardprozess Installation->Analyse->Freigaben->Doku")
    workflow.add_argument("--server", default="", help="Kommagetrennte Serverliste")
    workflow.add_argument("--rollen", default="APP", help="Standardrollen")
    workflow.add_argument("--deklaration", default="", help="Rollendeklaration pro Server")
    workflow.add_argument("--basis", required=True, help="SystemAG-Basispfad für Ordner/Freigaben")
    workflow.add_argument("--out", default="docs/serverbericht.md", help="Markdown-Bericht der Analyse")
    workflow.add_argument("--logs", default="logs", help="Log-Verzeichnis für Doku-Konsolidierung")
    workflow.add_argument("--docs", default="docs", help="Zielordner für Log-Dokumentation")
    workflow.add_argument("--share-auto-anwenden", action="store_true", help="Share-Änderungen ohne Rückfrage anwenden")
    workflow.add_argument("--share-policy-kopie", action="store_true", help="Optionale _Kopie-Struktur ergänzen")
    workflow.add_argument(
        "--share-policy-doku",
        action="store_true",
        help="Optionale Dokumentation-Unterordner (Analysen/Aenderungen) ergänzen",
    )

    ordner = sub.add_parser("ordner-check", help="SystemAG-Struktur prüfen oder anlegen")
    ordner.add_argument("--basis", required=True, help="Basisordner, z. B. D:/SystemAG")
    ordner.add_argument("--anlegen", action="store_true", help="Fehlende Ordner direkt anlegen")

    return parser


def _parse_discovery_range_text(range_text: str) -> DiscoveryRangeSegment:
    """Parst ein Segment aus dem Format `A.B.C.X-Y` in ein DiscoveryRangeSegment."""
    rohwert = range_text.strip()
    if not rohwert:
        raise ValueError("Leerer Discovery-Range ist nicht erlaubt.")

    if "-" not in rohwert:
        raise ValueError("Discovery-Range muss einen Start-/Endbereich enthalten (X-Y).")

    host_teil, end_text = rohwert.rsplit("-", maxsplit=1)
    oktette = host_teil.split(".")
    if len(oktette) != 4 or not all(teil.isdigit() for teil in oktette):
        raise ValueError(f"Ungültiger Discovery-Range: {rohwert}")

    basis = ".".join(oktette[:3])
    start = int(oktette[3])
    ende = int(end_text)
    return DiscoveryRangeSegment(basis=basis, start=start, ende=ende)


def _ermittle_serverliste(args: argparse.Namespace) -> list[str]:
    """Baut die effektive Serverliste aus manuellen Angaben und erweiterter Discovery."""
    server_liste = parse_liste(args.server)

    # Kompatibilitätsmodus: bestehende Einzel-Range-Flags bleiben erhalten.
    if args.discover_base:
        gefundene_server = entdecke_server_kandidaten(
            basis=args.discover_base,
            start=args.discover_start,
            ende=args.discover_end,
        )
        for server in gefundene_server:
            if server not in server_liste:
                server_liste.append(server)

    if args.discover_range:
        ranges = [_parse_discovery_range_text(eintrag) for eintrag in args.discover_range]
        ergebnisse = entdecke_server_mehrere_ranges(ranges=ranges, konfiguration=DiscoveryKonfiguration())
        for treffer in ergebnisse:
            if treffer.hostname not in server_liste:
                server_liste.append(treffer.hostname)

    if args.discover_seed or args.discover_seeds_from_ad_dns:
        konfiguration = DiscoveryKonfiguration(nutze_ad_ldap=args.discover_seeds_from_ad_dns)
        ergebnisse = entdecke_server_via_seeds(seeds=args.discover_seed, konfiguration=konfiguration)
        for treffer in ergebnisse:
            if treffer.hostname not in server_liste:
                server_liste.append(treffer.hostname)

    return server_liste


def main() -> int:
    """Startet die CLI und führt den ausgewählten Arbeitsmodus aus."""
    parser = baue_parser()
    args = parser.parse_args()
    lauf_id = erstelle_lauf_id()
    setze_lauf_id(lauf_id)
    logger.info("CLI gestartet mit Kommando: %s", args.kommando)

    if args.kommando == "scan":
        try:
            server_liste = _ermittle_serverliste(args)
        except ValueError as exc:
            parser.error(f"Ungültige Discovery-Eingabe: {exc}")
        if not server_liste:
            parser.error("Mindestens ein gültiger Servername oder Discovery-Parameter muss angegeben werden.")

        standard_rollen = parse_liste(args.rollen, to_upper=True)
        ziele = baue_serverziele(server_liste, parse_deklarationen(args.deklaration), standard_rollen)
        ergebnisse = analysiere_mehrere_server(ziele, lauf_id=lauf_id)

        Path(args.out).write_text(render_markdown(ergebnisse), encoding="utf-8")
        logger.info("Markdown-Dokumentation erstellt: %s", args.out)
        print(f"Markdown-Dokumentation erstellt: {args.out}")
        print(f"Lauf-ID: {lauf_id}")
        return 0

    if args.kommando == "workflow":
        server_liste = parse_liste(args.server)
        if not server_liste:
            parser.error("Für den Workflow muss mindestens ein Server angegeben werden (--server).")

        ziele = baue_serverziele(
            server_liste,
            parse_deklarationen(args.deklaration),
            parse_liste(args.rollen, to_upper=True),
        )

        def _progress(schritt: WorkflowSchritt, prozent: int, text: str) -> None:
            print(f"[{prozent:>3}%] {schritt.value}: {text}")

        share_policy = SharePolicy(
            erstelle_systemag_kopie=args.share_policy_kopie,
            erstelle_doku_unterordner=args.share_policy_doku,
        )

        ergebnis = fuehre_standard_workflow_aus(
            ziele=ziele,
            basis_pfad=Path(args.basis),
            report_pfad=Path(args.out),
            logs_verzeichnis=Path(args.logs),
            docs_verzeichnis=Path(args.docs),
            lauf_id=lauf_id,
            progress=_progress,
            share_bestaetigung=None if args.share_auto_anwenden else bestaetige_aenderungen_cli,
            share_policy=share_policy,
        )
        print(f"Workflow abgeschlossen: {'erfolgreich' if ergebnis.erfolgreich else 'mit Fehlern'}")
        return 0 if ergebnis.erfolgreich else 2

    if args.kommando == "ordner-check":
        basis = Path(args.basis)
        fehlend = ermittle_fehlende_ordner(basis)
        if not fehlend:
            print("Alle Zielordner sind bereits vorhanden.")
            return 0

        print("Fehlende Ordner:")
        for pfad in fehlend:
            print(f"- {pfad}")

        if args.anlegen:
            lege_ordner_an(fehlend)
            print("Fehlende Ordner wurden angelegt.")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
