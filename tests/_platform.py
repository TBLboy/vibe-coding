"""Platform helpers shared by the OpenCode framework test modules (TASK-101).

The file is deliberately *not* named ``test_*.py`` so unittest discovery skips
it. It is importable both when discovery runs from the repository root
(``python -m unittest discover -s tests``) and when a single module is run from
inside ``tests/`` (``python -m unittest test_x``); each test module inserts this
directory into ``sys.path`` before importing it.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


# --- symlink capability ------------------------------------------------------

_SYMLINK_CAPABLE: bool | None = None


def can_symlink() -> bool:
    """Whether this host can create both a file and a directory symlink.

    Windows without Developer Mode or administrator raises ``OSError`` with
    ``WinError 1314`` ("A required privilege is not held by the client"). The
    probe runs once, caches its answer, and removes its temporary artifacts.
    """
    global _SYMLINK_CAPABLE
    if _SYMLINK_CAPABLE is None:
        capable = False
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target_file = root / "probe-target.txt"
            target_file.write_text("probe", encoding="utf-8")
            target_dir = root / "probe-target-dir"
            target_dir.mkdir()
            try:
                os.symlink(target_file, root / "probe-file-link.txt")
                os.symlink(target_dir, root / "probe-dir-link", target_is_directory=True)
                capable = True
            except (OSError, NotImplementedError):
                capable = False
        _SYMLINK_CAPABLE = capable
    return _SYMLINK_CAPABLE


skip_unless_symlink = unittest.skipUnless(
    can_symlink(),
    "symlink creation needs a privilege this host does not have "
    "(Windows without Developer Mode/administrator raises OSError WinError 1314)",
)
"""Skip a whole test when the host cannot create symlinks (Windows, no privilege)."""

posix_only = unittest.skipUnless(
    os.name == "posix",
    "POSIX-only assertion: this host has no POSIX permission bits",
)
"""Skip a whole test that only makes sense where POSIX permission bits exist."""


# --- fake package-manager shims ----------------------------------------------


def make_package_manager_shim(bin_dir: Path, name: str, body: str) -> Path:
    """Create a runnable fake ``npm``/``bun`` that ``shutil.which`` finds.

    ``body`` is Python source for the launcher and must end with
    ``sys.exit(<code>)`` so the shim's exit status reaches the caller. On POSIX
    the launcher is ``<bin_dir>/<name>`` with a ``sys.executable`` shebang; on
    Windows it is ``<bin_dir>/<name>.py`` plus a ``<name>.cmd`` batch launcher
    that forwards every argument (``%*``). Windows has no executable bit, so no
    ``chmod`` is attempted there. Returns the launcher path that PATH lookup
    resolves.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        script = bin_dir / f"{name}.py"
        script.write_text(body, encoding="utf-8")
        launcher = bin_dir / f"{name}.cmd"
        launcher.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "%~dp0{name}.py" %*\r\n',
            encoding="utf-8",
        )
        return launcher
    launcher = bin_dir / name
    launcher.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    launcher.chmod(0o700)
    return launcher


# --- bash resolution ---------------------------------------------------------


def usable_posix_bash() -> str | None:
    """Return a bash that can run the launcher with native paths, or None.

    On Windows the PATH normally holds the WSL stub. It runs commands inside a
    Linux namespace, so a native Windows path argument never resolves and the
    launcher cannot be exercised through it without separate wslpath translation.
    That is a host limitation, not a launcher defect, so the bash check is
    skipped instead of reported as a failure.
    """
    bash = shutil.which("bash")
    if bash is None:
        return None
    probe = subprocess.run(
        [bash, "-c", "printf vibe-bash-probe"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if probe.returncode != 0 or probe.stdout != b"vibe-bash-probe":
        return None
    # A bash inside WSL exposes wslpath; it cannot take a native Windows path.
    in_wsl = subprocess.run(
        [bash, "-c", "command -v wslpath"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if in_wsl.returncode == 0:
        return None
    return bash


# --- self-contained @opencode-ai/plugin shim ---------------------------------


def make_opencode_ai_node_modules(parent: Path) -> Path:
    """Materialise a self-contained ``node_modules`` for the plugin tests.

    The real ``@opencode-ai/plugin`` entry point re-exports ``tool`` (a
    pass-through that returns its input) with ``tool.schema`` bound to a schema
    builder. The plugin under test imports exactly those names. Reproducing the
    same shape from the repository tree removes the tests' dependency on the
    machine's global ``~/.config/opencode/node_modules`` and avoids needing a
    symlink privilege on Windows. Returns the created ``node_modules`` directory.
    """
    package = parent / "node_modules" / "@opencode-ai" / "plugin"
    package.mkdir(parents=True, exist_ok=True)
    (package / "package.json").write_text(
        "{\n"
        '  "name": "@opencode-ai/plugin",\n'
        '  "version": "0.0.0-vibe-test-shim",\n'
        '  "type": "module",\n'
        '  "main": "index.js",\n'
        '  "exports": { ".": "./index.js" }\n'
        "}\n",
        encoding="utf-8",
    )
    (package / "index.js").write_text(
        "export function tool(input) { return input; }\n"
        "function schemaNode() {\n"
        "  const self = {};\n"
        "  self.optional = () => self;\n"
        "  self.nullable = () => self;\n"
        "  self.describe = () => self;\n"
        "  self.default = () => self;\n"
        "  return self;\n"
        "}\n"
        "tool.schema = {\n"
        "  string: () => schemaNode(),\n"
        "  number: () => schemaNode(),\n"
        "  boolean: () => schemaNode(),\n"
        "  object: () => schemaNode(),\n"
        "};\n",
        encoding="utf-8",
    )
    return parent / "node_modules"
