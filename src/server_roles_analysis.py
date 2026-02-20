"""Legacy-Einstieg für Serverrollenanalyse (deprecated).

Dieses Modul enthält **keine eigene Analyselogik** mehr.
Es dient ausschließlich als Kompatibilitäts-Wrapper auf die aktuellen
Einstiegspunkte:

- ``systemmanager_sagehelper.analyzer`` für programmatische Analysen
- ``server_analysis_gui`` für den GUI-Start
- ``systemmanager_sagehelper.cli`` für den CLI-Start
"""

from __future__ import annotations

import argparse
import logging
import os
import warnings
from dataclasses import asdict

from systemmanager_sagehelper.analyzer import analysiere_mehrere_server
from systemmanager_sagehelper.models import ServerZiel

LEGACY_HINWEIS = (
    "`src/server_roles_analysis.py` ist veraltet und für produktive Nutzung gesperrt. "
    "Verwenden Sie stattdessen `server_analysis_gui.py` oder `python -m systemmanager_sagehelper`."
)

logging.basicConfig(
    filename=os.path.join(os.getcwd(), "logs/server_roles_analysis.log"),
    level=logging.WARNING,
    format="[%(asctime)s] %(message)s",
)


def _protokolliere_und_warne_deprecation() -> None:
    """Gibt einen einheitlichen Deprecation-Hinweis auf Konsole und im Log aus."""
    logging.warning(LEGACY_HINWEIS)
    warnings.warn(LEGACY_HINWEIS, category=DeprecationWarning, stacklevel=2)


def analyze_server_roles(servernamen: list[str], standard_rollen: list[str] | None = None) -> list[dict[str, object]]:
    """Legacy-API als dünner Wrapper ohne eigene Rollenheuristik.

    Wichtig: Diese Funktion enthält absichtlich keine Dummy-Logik,
    sondern delegiert vollständig an ``systemmanager_sagehelper.analyzer``.
    """
    _protokolliere_und_warne_deprecation()

    normalisierte_rollen = [rolle.strip().upper() for rolle in (standard_rollen or ["APP"]) if rolle.strip()]
    ziele = [
        ServerZiel(name=name.strip(), rollen=normalisierte_rollen, rollenquelle="legacy-wrapper")
        for name in servernamen
        if name.strip()
    ]
    ergebnisse = analysiere_mehrere_server(ziele)
    return [asdict(eintrag) for eintrag in ergebnisse]


def _starte_gui_wrapper() -> int:
    """Leitet den Legacy-Einstieg kontrolliert auf die aktuelle GUI weiter."""
    from server_analysis_gui import main as gui_main

    _protokolliere_und_warne_deprecation()
    gui_main()
    return 0


def _starte_cli_wrapper(rest_args: list[str]) -> int:
    """Leitet den Legacy-Einstieg kontrolliert auf die aktuelle CLI weiter."""
    import sys
    from systemmanager_sagehelper.cli import main as cli_main

    _protokolliere_und_warne_deprecation()
    alter_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], *rest_args]
        return int(cli_main())
    finally:
        sys.argv = alter_argv


def main(argv: list[str] | None = None) -> int:
    """Standardverhalten: produktive Nutzung blockieren, optional sauber weiterleiten.

    Ohne Wrapper-Flag wird der Einstieg explizit beendet,
    damit keine neue produktive Nutzung auf diesem Legacy-Modul entsteht.
    """
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--legacy-wrapper",
        choices=("gui", "cli"),
        help="Nur für Abwärtskompatibilität: an die aktuelle GUI oder CLI weiterleiten.",
    )
    args, rest_args = parser.parse_known_args(argv)

    if args.legacy_wrapper == "gui":
        return _starte_gui_wrapper()
    if args.legacy_wrapper == "cli":
        return _starte_cli_wrapper(rest_args)

    _protokolliere_und_warne_deprecation()
    print(f"⚠️ {LEGACY_HINWEIS}")
    print("Ausführung beendet. Für GUI: `python src/server_analysis_gui.py`.")
    print("Für CLI: `python -m systemmanager_sagehelper scan --help`.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
