"""Unit tests for the next_bump release helper."""

from pathlib import Path

import pytest

from scripts.next_bump import (
    NoChangesError,
    bumped_version,
    current_version,
    determine_bump,
    fragment_types,
    main,
)


def _write_fragments(directory: Path, *names: str) -> None:
    """Create towncrier fragments with the given file names."""
    for name in names:
        (directory / name).write_text("Some change.\n")


def _write_project(root: Path, version: str, *names: str) -> None:
    """Create a project root with a setup.cfg and pending change fragments."""
    (root / "setup.cfg").write_text(f"[bumpversion]\ncurrent_version = {version}\n")
    (root / "changes").mkdir()
    _write_fragments(root / "changes", *names)


def test_fragment_types_reads_change_type_from_file_name(tmp_path: Path) -> None:
    """Test the change type is taken from the second part of the file name."""
    _write_fragments(tmp_path, "292.feature.rst", "303.bugfix.rst")

    assert fragment_types(tmp_path) == {"bugfix", "feature"}


def test_fragment_types_accepts_name_variants(tmp_path: Path) -> None:
    """Test fragments without .rst suffix, with a counter, and with a non-numeric issue."""
    _write_fragments(
        tmp_path,
        "290.feature",
        "267.misc.1",
        "ghsa-94v4-2fvf-ff8p.bugfix.rst",
    )

    assert fragment_types(tmp_path) == {"bugfix", "feature", "misc"}


def test_fragment_types_ignores_non_fragments(tmp_path: Path) -> None:
    """Test files that are not change fragments are ignored."""
    _write_fragments(tmp_path, "292.feature.rst", ".gitignore", "README")

    assert fragment_types(tmp_path) == {"feature"}


def test_feature_gives_minor() -> None:
    """Test a new feature requires a minor bump."""
    assert determine_bump({"feature", "bugfix", "misc"}, "0.47.1") == "minor"


def test_bugfix_only_gives_patch() -> None:
    """Test changes without a feature or removal require a patch bump."""
    assert determine_bump({"bugfix", "doc", "misc"}, "0.47.1") == "patch"


def test_removal_gives_minor_before_1_0() -> None:
    """Test a removal requires a minor bump while the major version is 0."""
    assert determine_bump({"removal"}, "0.47.1") == "minor"


def test_removal_gives_major_from_1_0() -> None:
    """Test a removal requires a major bump once the major version is 1 or higher."""
    assert determine_bump({"removal", "feature"}, "1.2.3") == "major"


def test_api_breakage_gives_minor_before_1_0() -> None:
    """Test a breaking API change raises a patch bump to minor while the major version is 0."""
    assert determine_bump({"bugfix"}, "0.47.1", api_broken=True) == "minor"


def test_api_breakage_gives_major_from_1_0() -> None:
    """Test a breaking API change requires a major bump once the major version is 1 or higher."""
    assert determine_bump({"feature"}, "1.2.3", api_broken=True) == "major"


@pytest.mark.parametrize(
    "bump, expected",
    [("major", "1.0.0"), ("minor", "0.48.0"), ("patch", "0.47.2")],
)
def test_bumped_version(bump: str, expected: str) -> None:
    """Test the lower parts of the version are reset by a bump."""
    assert bumped_version("0.47.1", bump) == expected


def test_no_fragments_raises() -> None:
    """Test releasing without any change fragment is refused."""
    with pytest.raises(NoChangesError):
        determine_bump(set(), "0.47.1")


def test_current_version_is_read_from_setup_cfg(tmp_path: Path) -> None:
    """Test the current version is read from the bumpversion section."""
    (tmp_path / "setup.cfg").write_text("[bumpversion]\ncurrent_version = 0.47.1\ncommit = True\n")

    assert current_version(tmp_path / "setup.cfg") == "0.47.1"


def test_main_prints_version_on_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the new version is printed on stdout, so it can be passed to towncrier and bump2version."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")

    assert main(tmp_path) == 0
    assert capsys.readouterr().out == "0.48.0\n"


def test_main_reports_what_it_based_the_bump_on(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the pending change types are reported on stderr."""
    _write_project(tmp_path, "0.47.1", "303.bugfix.rst", "291.misc.rst")

    assert main(tmp_path) == 0
    assert "bugfix, misc" in capsys.readouterr().err


def test_main_fails_without_pending_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test main fails instead of proposing a bump when there is nothing to release."""
    _write_project(tmp_path, "0.47.1")

    assert main(tmp_path) == 1
    assert capsys.readouterr().out == ""


def test_main_reports_proposed_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the version the bump leads to is reported on stderr."""
    _write_project(tmp_path, "0.47.1", "292.feature.rst")

    assert main(tmp_path) == 0
    assert "minor (0.47.1 -> 0.48.0)" in capsys.readouterr().err


def test_main_ci_writes_job_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the proposal is appended to the GitHub Actions job summary with --ci."""
    _write_project(tmp_path, "0.47.1", "303.bugfix.rst")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert main(tmp_path, ["--ci"]) == 0
    assert "patch (0.47.1 -> 0.47.2)" in summary.read_text()


def test_main_ci_does_not_fail_without_pending_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test having nothing to release is not an error with --ci."""
    _write_project(tmp_path, "0.47.1")

    assert main(tmp_path, ["--ci"]) == 0
    assert capsys.readouterr().out == ""
