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


# The remembered archive root lives next to this Skill in the *installed* copy
# (~/.config/opencode/skills/a-project-archive/archive_root.conf). It is user data:
# the installer never ships it, so reinstall/uninstall leave it alone.
CONFIG_FILE = Path(__file__).resolve().parent.parent / "archive_root.conf"
EXIT_UNCONFIGURED = 3


def load_archive_root(config_file: Path | None = None) -> Path | None:
    config_file = config_file or CONFIG_FILE
    try:
        value = config_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(value) if value else None


def save_archive_root(root: Path, config_file: Path | None = None) -> Path:
    config_file = config_file or CONFIG_FILE
    resolved = root.expanduser()
    if not resolved.is_absolute():
        raise ValueError(f"archive root must be an absolute path: {root}")
    resolved = resolved.resolve()
    if not resolved.is_dir():
        raise ValueError(f"archive root does not exist or is not a directory: {resolved}")
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(str(resolved) + "\n", encoding="utf-8")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, help="project to archive (required unless only setting the root)")
    parser.add_argument("--archive-root", type=Path, help="one-off destination; overrides the remembered root without saving it")
    parser.add_argument("--set-archive-root", type=Path, metavar="PATH", help="remember PATH as the default archive root for this machine")
    parser.add_argument("--show-archive-root", action="store_true", help="print the remembered archive root and exit")
    args = parser.parse_args()
    try:
        if args.show_archive_root:
            root = load_archive_root()
            print(json.dumps({"archive_root": str(root) if root else None, "config": str(CONFIG_FILE)}, ensure_ascii=False))
            return 0 if root else EXIT_UNCONFIGURED
        if args.set_archive_root is not None:
            saved = save_archive_root(args.set_archive_root)
            print(json.dumps({"archive_root": str(saved), "config": str(CONFIG_FILE)}, ensure_ascii=False))
            if args.project_root is None:
                return 0
        if args.project_root is None:
            parser.error("--project-root is required to archive")
        root = args.archive_root or load_archive_root()
        if root is None:
            print(
                "[!] No archive root is configured and none was given. Ask the user for the absolute archive "
                f"directory, then run again with --set-archive-root <path> (saved to {CONFIG_FILE}).",
                file=sys.stderr,
            )
            return EXIT_UNCONFIGURED
        target = archive(args.project_root, root)
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1
    print(json.dumps({"archive": str(target), "archive_root": str(root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
