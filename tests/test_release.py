"""Unit tests for the release helper."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts.release import Runner, main, release_commands


def _recorder() -> tuple[list[list[str]], Runner]:
    """Get a runner which records the commands instead of running them."""
    commands: list[list[str]] = []

    def runner(command: Sequence[str], _root: Path) -> None:
        commands.append(list(command))

    return commands, runner


def _write_project(root: Path, version: str, *names: str) -> None:
    """Create a committed project with a setup.cfg and pending change fragments."""
    (root / "setup.cfg").write_text(f"[bumpversion]\ncurrent_version = {version}\n")
    (root / "changes").mkdir()
    for name in names:
        (root / "changes" / name).write_text("Some change.\n")
    for command in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *command], cwd=root, check=True)


def test_release_commands_use_the_version_for_changelog_and_tag() -> None:
    """Test towncrier and bump2version get the same version."""
    towncrier, commit, bumpversion = release_commands("0.48.0")

    assert towncrier[-2:] == ["--version", "0.48.0"]
    assert commit == ["git", "commit", "-m", "Towncrier"]
    assert bumpversion[-4:] == ["--tag", "--new-version", "0.48.0", "patch"]


def test_main_releases_proposed_version(tmp_path: Path) -> None:
    """Test the proposed version is released when no version is given."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")
    commands, runner = _recorder()

    assert main(tmp_path, ["--yes"], runner) == 0
    assert commands[0][-1] == "0.48.0"
    assert commands[2][-2] == "0.48.0"


def test_main_releases_overridden_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test --version overrides the proposed version, and this is reported."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")
    commands, runner = _recorder()

    assert main(tmp_path, ["--yes", "--version", "1.0.0"], runner) == 0
    assert commands[0][-1] == "1.0.0"
    assert "instead of the proposed 0.48.0" in capsys.readouterr().out


def test_main_refuses_invalid_version(tmp_path: Path) -> None:
    """Test a version which is not major.minor.patch is refused."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")
    commands, runner = _recorder()

    assert main(tmp_path, ["--yes", "--version", "minor"], runner) == 1
    assert not commands


def test_main_refuses_without_pending_changes(tmp_path: Path) -> None:
    """Test nothing is released when there are no pending changes."""
    _write_project(tmp_path, "0.47.1")
    commands, runner = _recorder()

    assert main(tmp_path, ["--yes"], runner) == 1
    assert not commands


def test_main_refuses_uncommitted_changes(tmp_path: Path) -> None:
    """Test nothing is released while tracked files have uncommitted changes."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")
    (tmp_path / "setup.cfg").write_text("[bumpversion]\ncurrent_version = 0.47.1\ncommit = True\n")
    commands, runner = _recorder()

    assert main(tmp_path, ["--yes"], runner) == 1
    assert not commands


def test_main_asks_for_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test nothing is released when the confirmation is not answered with y."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")
    monkeypatch.setattr("builtins.input", lambda _: "")
    commands, runner = _recorder()

    assert main(tmp_path, [], runner) == 1
    assert not commands


def test_main_dry_run_runs_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test --dry-run only shows the commands."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")
    commands, runner = _recorder()

    assert main(tmp_path, ["--dry-run"], runner) == 0
    assert not commands
    assert "Would run:" in capsys.readouterr().out
