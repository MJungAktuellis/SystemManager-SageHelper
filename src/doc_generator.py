"""Legacy-Wrapper auf ``systemmanager_sagehelper.documentation``."""

from __future__ import annotations

from systemmanager_sagehelper.installation_state import pruefe_installationszustand, verarbeite_installations_guard
from systemmanager_sagehelper.documentation import (
    erstelle_dokumentation,
    generiere_markdown_bericht,
    lese_logs,
)

__all__ = ["lese_logs", "generiere_markdown_bericht", "erstelle_dokumentation"]


def main() -> None:
    """Direkter Einstieg mit Installationsschutz."""

    def _zeige_fehler(text: str) -> None:
        print(f"❌ {text}")

    def _frage_installation(_frage: str) -> bool:
        antwort = input("Installation starten? [j/N]: ").strip().lower()
        return antwort in {"j", "ja", "y", "yes"}

    freigegeben = verarbeite_installations_guard(
        pruefe_installationszustand(),
        modulname="Dokumentation",
        fehlermeldung_fn=_zeige_fehler,
        installationsfrage_fn=_frage_installation,
    )
    if not freigegeben:
        return

    erstelle_dokumentation("logs", "docs")


if __name__ == "__main__":
    main()
