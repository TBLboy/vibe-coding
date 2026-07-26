#!/usr/bin/env python3
"""Initialize the current project's Project Log without overwriting project files."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def iter_files(root: Path, items: list[str]):
    for item in items:
        path = root / item
        if path.is_file():
            yield path, path.relative_to(root)
        elif path.is_dir():
            for file in path.rglob("*"):
                if file.is_file():
                    yield file, file.relative_to(root)


def initialize_project(target: Path, dry_run: bool = False) -> tuple[list[Path], list[Path]]:
    runtime_root = Path(__file__).resolve().parents[1]
    source = runtime_root / "project-log-template"
    target = target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        raise FileNotFoundError(f"Project Log template is missing: {source}")
    created: list[Path] = []
    skipped: list[Path] = []
    for src, rel in iter_files(source, ["."]):
        rel = Path(".project-log") / rel
        dst = target / rel
        if dst.exists():
            skipped.append(rel)
            continue
        created.append(rel)
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return created, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    try:
        created, skipped = initialize_project(target, args.dry_run)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    print(
        f"Project Log target: {target}\n"
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
