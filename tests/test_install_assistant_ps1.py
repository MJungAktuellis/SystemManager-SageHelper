"""Regressionstests für den PowerShell-Installer-Launcher."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PS1_PATH = REPO_ROOT / "scripts" / "install_assistant.ps1"


def test_elevation_verwendet_argument_array_und_repo_workdir() -> None:
    """Der UAC-Neustart soll robust gequotet und im Repo-Kontext ausgeführt werden."""
    inhalt = PS1_PATH.read_text(encoding="utf-8")

    assert "$elevationArguments = @(" in inhalt
    assert '"-File", $PSCommandPath' in inhalt
    assert "-ArgumentList $elevationArguments" in inhalt
    assert "-WorkingDirectory $script:RepoRoot" in inhalt
