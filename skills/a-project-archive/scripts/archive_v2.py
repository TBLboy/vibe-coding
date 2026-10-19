#!/usr/bin/env python3
"""Create a copy-only V2 project-memory archive without external dependencies."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def safe_tree(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Unsafe or missing directory: {root}")
    files: list[Path] = []
    for base, directories, names in os.walk(root, followlinks=False):
        base_path = Path(base)
        for name in directories + names:
            candidate = base_path / name
            if candidate.is_symlink():
                raise ValueError(f"Symlink source is not allowed: {candidate}")
        files.extend(base_path / name for name in names)
    return sorted(files)


def contains(parent: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def archive(project_root: Path, archive_root: Path, now: datetime | None = None) -> Path:
    source = project_root.expanduser().resolve()
    destination_root = archive_root.expanduser().resolve()
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"Unsafe or missing project root: {project_root}")
    if contains(source, destination_root):
        raise ValueError("archive_root must be outside project_root")
    memory = source / ".vibe"
    if not memory.exists():
        raise ValueError("Missing .vibe directory; nothing to archive")
    memory_files = safe_tree(memory)
    agents = source / "AGENTS.md"
    if agents.exists() and (agents.is_symlink() or not agents.is_file()):
        raise ValueError(f"Unsafe AGENTS.md: {agents}")
    if not agents.exists() and not memory_files:
        raise ValueError("No archiveable V2 project memory")

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    parent = destination_root / source.name
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / stamp
    suffix = 1
    while target.exists():
        suffix += 1
        target = parent / f"{stamp}-{suffix}"
    staging = parent / f".{target.name}-{uuid.uuid4().hex}.tmp"
    try:
        staging.mkdir()
        copied: list[dict[str, str]] = []
        if agents.exists():
            shutil.copy2(agents, staging / "AGENTS.md")
            copied.append({"path": "AGENTS.md", "sha256": digest(staging / "AGENTS.md")})
        shutil.copytree(memory, staging / ".vibe", symlinks=False)
        for file in sorted((staging / ".vibe").rglob("*")):
            if file.is_file():
                copied.append({"path": file.relative_to(staging).as_posix(), "sha256": digest(file)})
        manifest = {
            "format": "vibe-v2-project-archive-1",
            "created_at": (now or datetime.now(timezone.utc)).isoformat(),
            "source": str(source),
            "files": copied,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for entry in copied:
            archived = staging / entry["path"]
            if not archived.is_file() or digest(archived) != entry["sha256"]:
                raise ValueError(f"Archive validation failed: {entry['path']}")
        staging.rename(target)
        return target
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--archive-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        target = archive(args.project_root, args.archive_root)
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1
    print(json.dumps({"archive": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
