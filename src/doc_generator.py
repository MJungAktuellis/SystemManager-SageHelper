"""Legacy-Wrapper auf ``systemmanager_sagehelper.documentation``."""

from __future__ import annotations

from systemmanager_sagehelper.documentation import (
    erstelle_dokumentation,
    generiere_markdown_bericht,
    lese_logs,
)

__all__ = ["lese_logs", "generiere_markdown_bericht", "erstelle_dokumentation"]


if __name__ == "__main__":
    erstelle_dokumentation("logs", "docs")
