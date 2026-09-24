#!/usr/bin/env python3
"""Initialize a project's Project Log without overwriting existing records.

Project Log format 2 (the transactional format) is the only supported format.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


LOG = Path(".project-log")
# The long-form summaries and the archive note are the only template files the
# transactional initialization copies; every other template entry was format 1.
SEED_FILES = (
    Path("current-session.md"),
    Path("progress.md"),
    Path("docs/archive/README.md"),
)
FORMAT_TWO_ENTRIES = (
    Path("state-format.json"),
    Path(".gitignore"),
    Path(".state"),
)


def template_root() -> Path:
    return Path(__file__).resolve().parents[1] / "project-log-template"


def _format_two_entries() -> list[Path]:
    return [LOG / entry for entry in FORMAT_TWO_ENTRIES] + [LOG / item for item in SEED_FILES]


def _initialize_format_two(target: Path, dry_run: bool) -> tuple[list[Path], list[Path]]:
    created = _format_two_entries()
    if dry_run:
        return created, []
    target.mkdir(parents=True, exist_ok=True)
    from state_context import initialize as initialize_state

    initialize_state(target)
    source = template_root()
    for relative in SEED_FILES:
        origin = source / relative
        if not origin.is_file():
            raise FileNotFoundError(f"Project Log template file is missing: {origin}")
        destination = target / LOG / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, destination)
    return created, []


def initialize_project(target: Path, dry_run: bool = False) -> tuple[list[Path], list[Path]]:
    """Create ``.project-log`` in format 2, never overwriting one that exists."""
    target = target.expanduser().resolve()
    log = target / LOG
    if log.exists() or log.is_symlink():
        return [], [LOG]
    return _initialize_format_two(target, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    try:
        created, skipped = initialize_project(target, args.dry_run)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print(
        f"Project Log target: {target}\n"
        f"Format: 2\n"
        f"Created: {len(created)}\n"
        f"Skipped existing: {len(skipped)}\n"
        f"Dry-run: {args.dry_run}\n"
    )
    for item in created:
        print("CREATE", item)
    for item in skipped:
        print("SKIP  ", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
