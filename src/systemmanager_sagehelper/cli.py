"""Kommandozeilen-Einstieg für Analyse, Strukturcheck und Markdown-Export."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import analysiere_server
from .folder_structure import ermittle_fehlende_ordner, lege_ordner_an
from .models import ServerZiel
from .report import render_markdown


def _parse_serverliste(wert: str) -> list[str]:
    return [eintrag.strip() for eintrag in wert.split(",") if eintrag.strip()]


def baue_parser() -> argparse.ArgumentParser:
    """Erstellt den CLI-Parser mit klaren Unterbefehlen."""
    parser = argparse.ArgumentParser(prog="sage-helper", description="Serveranalyse für Sage-Umgebungen")
    sub = parser.add_subparsers(dest="kommando", required=True)

    scan = sub.add_parser("scan", help="Server analysieren und Markdown erzeugen")
    scan.add_argument("--server", required=True, help="Kommagetrennte Serverliste, z. B. srv1,srv2")
    scan.add_argument("--rollen", default="APP", help="Kommagetrennte Rollen, z. B. SQL,APP,CTX")
    scan.add_argument("--out", default="dokumentation.md", help="Zieldatei für Markdown-Export")

    ordner = sub.add_parser("ordner-check", help="SystemAG-Struktur prüfen oder anlegen")
    ordner.add_argument("--basis", required=True, help="Basisordner, z. B. D:/SystemAG")
    ordner.add_argument("--anlegen", action="store_true", help="Fehlende Ordner direkt anlegen")

    return parser


def main() -> int:
    """Startet die CLI und führt den ausgewählten Arbeitsmodus aus."""
    parser = baue_parser()
    args = parser.parse_args()

    if args.kommando == "scan":
        rollen = _parse_serverliste(args.rollen)
        ergebnisse = []
        for server in _parse_serverliste(args.server):
            ergebnisse.append(analysiere_server(ServerZiel(name=server, rollen=rollen)))

        markdown = render_markdown(ergebnisse)
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"Markdown-Dokumentation erstellt: {args.out}")
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
