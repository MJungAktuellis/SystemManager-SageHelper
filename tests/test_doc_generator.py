"""Tests für Log-Konsolidierung im Dokumentationsgenerator."""

from __future__ import annotations

from pathlib import Path

from doc_generator import lese_logs


def test_lese_logs_beruecksichtigt_log_und_txt_dateien(tmp_path: Path) -> None:
    """Legacy-txt-Dateien sollen optional weiter unterstützt werden."""
    (tmp_path / "analyse.log").write_text("log-inhalt", encoding="utf-8")
    (tmp_path / "legacy.txt").write_text("txt-inhalt", encoding="utf-8")

    inhalt = lese_logs(str(tmp_path), include_altformate=True)

    assert "analyse.log" in inhalt
    assert "legacy.txt" in inhalt


def test_lese_logs_kann_altformat_abschalten(tmp_path: Path) -> None:
    """Bei deaktivierter Legacy-Unterstützung werden nur .log-Dateien geladen."""
    (tmp_path / "analyse.log").write_text("log-inhalt", encoding="utf-8")
    (tmp_path / "legacy.txt").write_text("txt-inhalt", encoding="utf-8")

    inhalt = lese_logs(str(tmp_path), include_altformate=False)

    assert "analyse.log" in inhalt
    assert "legacy.txt" not in inhalt
