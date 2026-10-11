#!/usr/bin/env python3
"""Release: build the changelog, bump the version and tag it.

The version is proposed by ``next_bump.py``, from the pending towncrier fragments and
a comparison of the public API with the latest release. Pass ``--version`` to release
another version instead.

Usage::

    $ python scripts/release.py
    $ python scripts/release.py --version 1.0.0

Nothing is pushed: check the result, then ``git push && git push --tags``.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

try:
    from scripts.next_bump import propose
except ImportError:  # Run as a script: scripts/ itself is on the path, not the project root
    from next_bump import propose  # type: ignore[no-redef]

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

Runner = Callable[[Sequence[str], Path], None]


def release_commands(version: str) -> list[list[str]]:
    """Get the commands which release the given version."""
    return [
        [sys.executable, "-m", "towncrier", "build", "--yes", "--version", version],
        ["git", "commit", "-m", "Towncrier"],
        # The part is required by bump2version, but not used with --new-version
        [sys.executable, "-m", "bumpversion", "--tag", "--new-version", version, "patch"],
    ]


def is_clean(root: Path) -> bool:
    """Check there are no uncommitted changes to tracked files."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, capture_output=True, text=True, check=True
    )
    return not result.stdout.strip()


def run_command(command: Sequence[str], root: Path) -> None:
    """Run a command in the project root, raise if it fails."""
    subprocess.run(command, cwd=root, check=True)


def main(root: Path | None = None, argv: list[str] | None = None, runner: Runner = run_command) -> int:
    """Release the proposed version, or the one given with --version."""
    parser = argparse.ArgumentParser(description="Build the changelog, bump the version and tag it.")
    parser.add_argument("--version", help="release this version instead of the proposed one")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="only show what would be done")
    args = parser.parse_args(argv or [])

    root = root or Path(__file__).resolve().parent.parent
    proposed, report = propose(root)
    print("\n".join(report))
    if proposed is None:
        return 1

    version = args.version or proposed
    if not VERSION_RE.fullmatch(version):
        print(f"Not a version number: {version}", file=sys.stderr)
        return 1
    if version != proposed:
        print(f"Overridden: releasing {version} instead of the proposed {proposed}")

    commands = release_commands(version)
    if args.dry_run:
        for command in commands:
            print("Would run:", " ".join(command))
        return 0

    if not is_clean(root):
        print("There are uncommitted changes, commit or stash them first", file=sys.stderr)
        return 1
    if not args.yes and input(f"Release {version}? [y/N] ").strip().lower() != "y":
        print("Not released")
        return 1

    for command in commands:
        runner(command, root)
    print(f"Released {version}, not pushed: git push && git push --tags")
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
