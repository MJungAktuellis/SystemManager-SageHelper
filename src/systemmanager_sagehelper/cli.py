"""Kommandozeilen-Einstieg für Analyse, Strukturcheck und Markdown-Export."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import analysiere_mehrere_server, entdecke_server_kandidaten
from .folder_structure import ermittle_fehlende_ordner, lege_ordner_an
from .logging_setup import erstelle_lauf_id, konfiguriere_logger, setze_lauf_id
from .models import ServerZiel
from .report import render_markdown

logger = konfiguriere_logger(__name__, dateiname="cli.log")


def _parse_liste(wert: str, *, to_upper: bool = False) -> list[str]:
    """Parst kommaseparierte Werte, entfernt Leerwerte/Duplikate und behält Reihenfolge."""
    eintraege: list[str] = []
    for rohwert in wert.split(","):
        kandidat = rohwert.strip()
        if to_upper:
            kandidat = kandidat.upper()
        if kandidat and kandidat not in eintraege:
            eintraege.append(kandidat)
    return eintraege


def _parse_deklarationen(wert: str) -> dict[str, list[str]]:
    """Parst Deklarationen im Format 'srv1=SQL,APP;srv2=CTX'."""
    deklarationen: dict[str, list[str]] = {}
    for block in wert.split(";"):
        if "=" not in block:
            continue
        server, rollen = block.split("=", 1)
        server_name = server.strip()
        if not server_name:
            continue
        deklarationen[server_name] = _parse_liste(rollen, to_upper=True)
    return deklarationen


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
    scan.add_argument(
        "--discover-base",
        default="",
        help="IPv4-Basis für Discovery, z. B. 192.168.10",
    )
    scan.add_argument("--discover-start", type=int, default=1, help="Start-Hostnummer für Discovery")
    scan.add_argument("--discover-end", type=int, default=20, help="End-Hostnummer für Discovery")
    scan.add_argument("--out", default="dokumentation.md", help="Zieldatei für Markdown-Export")

    ordner = sub.add_parser("ordner-check", help="SystemAG-Struktur prüfen oder anlegen")
    ordner.add_argument("--basis", required=True, help="Basisordner, z. B. D:/SystemAG")
    ordner.add_argument("--anlegen", action="store_true", help="Fehlende Ordner direkt anlegen")

    return parser


def main() -> int:
    """Startet die CLI und führt den ausgewählten Arbeitsmodus aus."""
    parser = baue_parser()
    args = parser.parse_args()
    lauf_id = erstelle_lauf_id()
    setze_lauf_id(lauf_id)
    logger.info("CLI gestartet mit Kommando: %s", args.kommando)

    if args.kommando == "scan":
        server_liste = _parse_liste(args.server)

        if args.discover_base:
            gefundene_server = entdecke_server_kandidaten(
                basis=args.discover_base,
                start=args.discover_start,
                ende=args.discover_end,
            )
            for server in gefundene_server:
                if server not in server_liste:
                    server_liste.append(server)

        if not server_liste:
            parser.error("Mindestens ein gültiger Servername oder Discovery-Parameter muss angegeben werden.")

        standard_rollen = _parse_liste(args.rollen, to_upper=True)
        deklarationen = _parse_deklarationen(args.deklaration)

        ziele = [
            ServerZiel(name=server, rollen=deklarationen.get(server, standard_rollen))
            for server in server_liste
        ]

        ergebnisse = analysiere_mehrere_server(ziele, lauf_id=lauf_id)
        markdown = render_markdown(ergebnisse)
        Path(args.out).write_text(markdown, encoding="utf-8")
        logger.info("Markdown-Dokumentation erstellt: %s", args.out)
        print(f"Markdown-Dokumentation erstellt: {args.out}")
        print(f"Lauf-ID: {lauf_id}")
        return 0

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
