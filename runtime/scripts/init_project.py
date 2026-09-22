#!/usr/bin/env python3
"""Initialize a project's Project Log without overwriting existing records.

Format 2 (the transactional format) is the default. ``--format 1`` still writes the
legacy template for the migration window and for compatibility tests; it is not the
default and is retired through the stages described in
``.project-log/specs/framework-landing-contract.md``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


LOG = Path(".project-log")
# The long-form summaries and the archive note are format-agnostic, so both formats
# share one shipped copy instead of keeping two texts that can drift apart.
SEED_FILES = (
    Path("current-session.md"),
    Path("progress.md"),
    Path("docs/archive/README.md"),
)
FORMAT_TWO_ENTRIES = (
    Path("state-format.json"),
    Path(".gitignore"),
    Path(".state"),
    Path("exchange/.gitattributes"),
)


def template_root() -> Path:
    return Path(__file__).resolve().parents[1] / "project-log-template"


def iter_files(root: Path, items: list[str]):
    for item in items:
        path = root / item
        if path.is_file():
            yield path, path.relative_to(root)
        elif path.is_dir():
            for file in path.rglob("*"):
                if file.is_file():
                    yield file, file.relative_to(root)


def _legacy_entries() -> list[Path]:
    return [LOG / relative for _source, relative in iter_files(template_root(), ["."])]


def _format_two_entries() -> list[Path]:
    return [LOG / entry for entry in FORMAT_TWO_ENTRIES] + [LOG / item for item in SEED_FILES]


def _initialize_legacy(target: Path, dry_run: bool) -> tuple[list[Path], list[Path]]:
    source = template_root()
    if not source.exists():
        raise FileNotFoundError(f"Project Log template is missing: {source}")
    created: list[Path] = []
    skipped: list[Path] = []
    for src, rel in iter_files(source, ["."]):
        rel = LOG / rel
        dst = target / rel
        if dst.exists():
            skipped.append(rel)
            continue
        created.append(rel)
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return created, skipped


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


def initialize_project(
    target: Path, dry_run: bool = False, format: int = 2
) -> tuple[list[Path], list[Path]]:
    """Create ``.project-log`` in the requested format, never overwriting one that exists."""
    target = target.expanduser().resolve()
    log = target / LOG
    if log.exists() or log.is_symlink():
        return [], [LOG]
    if format == 2:
        return _initialize_format_two(target, dry_run)
    if format == 1:
        return _initialize_legacy(target, dry_run)
    raise ValueError(f"unsupported Project Log format: {format!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    try:
        created, skipped = initialize_project(target, args.dry_run, args.format)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print(
        f"Project Log target: {target}\n"
        f"Format: {args.format}\n"
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
