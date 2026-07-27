#!/usr/bin/env python3
"""Validate, test, and create a deterministic Vibe Coding Codex release ZIP."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


VERSION = "0.4.1"
EXCLUDED_DIRS = {".git", "__pycache__", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}


def include(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return (
        path.is_file()
        and not any(part in EXCLUDED_DIRS for part in relative.parts)
        and path.suffix not in EXCLUDED_SUFFIXES
    )


def run_checked(command: list[str], root: Path) -> None:
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    root = Path(__file__).resolve().parent
    run_checked(
        [sys.executable, "runtime/scripts/validate_package.py", "--root", "."],
        root,
    )
    run_checked([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], root)

    plugin_validator = (
        Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    plugin = root / "plugins" / "vibe-toolbelt"
    if plugin_validator.is_file():
        run_checked([sys.executable, str(plugin_validator), str(plugin)], root)

    output = root / "dist"
    output.mkdir(exist_ok=True)
    archive = output / f"vibe-coding-codex-global-core-{VERSION}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for path in sorted(root.rglob("*")):
            if not include(path, root):
                continue
            archive_name = Path(root.name) / path.relative_to(root)
            info = ZipInfo.from_file(path, arcname=archive_name.as_posix())
            info.date_time = (2026, 7, 26, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            package.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"Archive: {archive}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
