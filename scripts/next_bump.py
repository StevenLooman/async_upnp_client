#!/usr/bin/env python3
"""Propose the version number of the next release.

The change type of every pending towncrier fragment in ``changes/`` decides the bump:

- ``removal``: major, or minor while the major version is still 0
- ``feature``: minor
- anything else (``bugfix``, ``doc``, ``misc``): patch

The change type says which section of the changelog a change is printed under, not
what it does to the public API. So the public API is also compared to the latest
release with griffe, when griffe is installed (see ``tox -e griffe``). A breaking
change griffe finds raises the bump to what a ``removal`` gives. Griffe only sees
the API, not behaviour: treat the result as a proposal and override it when it is wrong.

The proposed version is printed on stdout, how it was decided on stderr. ``scripts/release.py``
releases with it. Usage::

    $ python scripts/next_bump.py

With ``--ci`` the proposal is also written to the GitHub Actions job summary, and
having nothing to release is not an error.
"""

import argparse
import configparser
import os
import subprocess
import sys
from pathlib import Path

CHANGE_TYPES = frozenset({"feature", "bugfix", "doc", "removal", "misc"})
PACKAGE = "async_upnp_client"


class NoChangesError(Exception):
    """Raised when there are no pending changes to release."""


def fragment_types(directory: Path) -> set[str]:
    """Get the change types of the towncrier fragments in directory."""
    types = set()
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue

        name_parts = path.name.split(".")
        if len(name_parts) > 1 and name_parts[1] in CHANGE_TYPES:
            types.add(name_parts[1])

    return types


def determine_bump(types: set[str], version: str, api_broken: bool = False) -> str:
    """Determine the bump for a release containing the given change types."""
    if not types:
        raise NoChangesError("No change fragments found, nothing to release")

    major = int(version.split(".")[0])
    if "removal" in types or api_broken:
        return "major" if major >= 1 else "minor"

    if "feature" in types:
        return "minor"

    return "patch"


def current_version(setup_cfg: Path) -> str:
    """Get the current version from the bumpversion section in setup.cfg."""
    parser = configparser.ConfigParser()
    parser.read(setup_cfg)
    return parser["bumpversion"]["current_version"]


def bumped_version(version: str, bump: str) -> str:
    """Get the version after bumping the given part."""
    major, minor, patch = (int(part) for part in version.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def latest_tag(root: Path) -> str | None:
    """Get the tag of the latest release, if root is a git repository with tags."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"], cwd=root, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def api_breakages(root: Path, ref: str) -> list[str] | None:
    """Get the breaking changes in the public API since ref, or None if griffe is not installed."""
    try:
        import griffe  # pylint: disable=import-outside-toplevel
    except ImportError:
        return None

    old = griffe.load_git(PACKAGE, ref=ref, repo=root)
    new = griffe.load(PACKAGE, search_paths=[root])
    return [
        breakage.explain(griffe.ExplanationStyle.MARKDOWN)
        for breakage in griffe.find_breaking_changes(old, new)
        # Every release changes the version
        if breakage.obj.name != "__version__"
    ]


def propose(root: Path) -> tuple[str | None, list[str]]:
    """Propose the version of the next release, None if there is nothing to release, and tell why."""
    version = current_version(root / "setup.cfg")
    types = fragment_types(root / "changes")

    report = []
    tag = latest_tag(root)
    breakages = api_breakages(root, tag) if tag else None
    if breakages is None:
        report.append("API check skipped: needs griffe and a release tag")
    else:
        report.append(f"API check against {tag}: {len(breakages)} breaking change(s)")
        report.extend(breakages)

    try:
        bump = determine_bump(types, version, bool(breakages))
    except NoChangesError as err:
        report.insert(0, str(err))
        return None, report

    new_version = bumped_version(version, bump)
    report.insert(0, f"{version}: pending changes: {', '.join(sorted(types))}")
    report.append(f"Proposed bump: {bump} ({version} -> {new_version})")
    return new_version, report


def main(root: Path | None = None, argv: list[str] | None = None) -> int:
    """Print the version of the next release on stdout, and how it was decided on stderr."""
    parser = argparse.ArgumentParser(description="Propose the version number of the next release.")
    parser.add_argument("--ci", action="store_true", help="write a job summary, do not fail when nothing to release")
    args = parser.parse_args(argv or [])

    root = root or Path(__file__).resolve().parent.parent
    new_version, report = propose(root)

    print("\n".join(report), file=sys.stderr)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if args.ci and summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("### Next version\n\n" + "\n\n".join(report) + "\n")

    if new_version is None:
        return 0 if args.ci else 1

    print(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
