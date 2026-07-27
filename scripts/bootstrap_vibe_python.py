#!/usr/bin/env python3
"""Create or repair the global Conda-backed Python environment for Vibe Coding."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

DEFAULT_ENV_NAME = "vibe-coding"
PYTHON_CONFIG_NAME = "vibe-python"


def codex_home(value: str | None) -> Path:
    raw = value or os.environ.get("CODEX_HOME")
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".codex").resolve()


def configured_python(home: Path) -> str | None:
    raw = os.environ.get("VIBE_PYTHON", "").strip()
    if not raw:
        path = home / PYTHON_CONFIG_NAME
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    raw = line
                    break
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        resolved = shutil.which(raw)
        candidate = Path(resolved) if resolved else candidate
    return str(candidate.resolve())


def run(command: Sequence[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=check,
    )


def python_is_usable(python: str, requirements: Path) -> tuple[bool, str]:
    probe = run(
        [
            python,
            "-c",
            "import sys, yaml, jsonschema; "
            "assert sys.version_info >= (3, 11); "
            "print(sys.executable)",
        ],
        check=False,
    )
    if probe.returncode == 0:
        return True, probe.stdout.strip().splitlines()[-1]
    return False, probe.stdout.strip() or f"unable to use {python}"


def find_conda() -> str | None:
    candidates = [
        os.environ.get("CONDA_EXE", ""),
        shutil.which("conda") or "",
        shutil.which("mamba") or "",
        str(Path.home() / "miniforge3/condabin/conda"),
        str(Path.home() / "mambaforge/condabin/conda"),
        str(Path.home() / "miniconda3/condabin/conda"),
    ]
    for raw in candidates:
        if raw and Path(raw).is_file() and os.access(raw, os.X_OK):
            return str(Path(raw).resolve())
    return None


def env_python(manager: str, env_name: str) -> str | None:
    result = run(
        [manager, "run", "-n", env_name, "python", "-c", "import sys; print(sys.executable)"],
        check=False,
    )
    if result.returncode:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else None


def create_env(manager: str, env_name: str) -> None:
    print(f"[*] Creating Conda environment {env_name!r} with Python 3.11+.", file=sys.stderr)
    result = run([manager, "create", "-y", "-n", env_name, "python=3.11"], check=False)
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or f"failed to create Conda environment {env_name!r}")


def install_requirements(python: str, requirements: Path) -> None:
    print(f"[*] Installing Vibe Python requirements into {python}.", file=sys.stderr)
    result = run([python, "-m", "pip", "install", "-r", str(requirements)], check=False)
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or "failed to install Vibe Python requirements")


def write_config(home: Path, python: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = home / PYTHON_CONFIG_NAME
    path.write_text(str(Path(python).resolve()) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def ensure_python(home: Path, requirements: Path, env_name: str, *, create: bool) -> str:
    selected = configured_python(home)
    if selected:
        usable, detail = python_is_usable(selected, requirements)
        if usable:
            return detail
        if not create:
            raise RuntimeError(f"Configured Vibe Python is unusable: {selected}\n{detail}")
        print(f"[!] Configured Vibe Python is unusable; attempting Conda repair: {detail}", file=sys.stderr)

    manager = find_conda()
    if not manager:
        if selected:
            raise RuntimeError(
                f"Configured Vibe Python is unusable and no Conda/Miniforge executable was found: {selected}"
            )
        raise RuntimeError(
            "No usable Vibe Python found. Install Miniforge/Miniconda or set VIBE_PYTHON to a Python 3.11+ environment."
        )

    python = env_python(manager, env_name)
    if not python:
        if not create:
            raise RuntimeError(f"Conda environment {env_name!r} was not found; refusing to create it during uninstall.")
        create_env(manager, env_name)
        python = env_python(manager, env_name)
    if not python:
        raise RuntimeError(f"Could not resolve Python from Conda environment {env_name!r}.")

    usable, detail = python_is_usable(python, requirements)
    if not usable:
        install_requirements(python, requirements)
        usable, detail = python_is_usable(python, requirements)
    if not usable:
        raise RuntimeError(f"Conda environment {env_name!r} remains unusable after dependency installation: {detail}")

    write_config(home, python)
    return detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home")
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--env-name", default=os.environ.get("VIBE_CONDA_ENV", DEFAULT_ENV_NAME))
    parser.add_argument("--no-create", action="store_true", help="Do not create a missing Conda environment.")
    parser.add_argument("--print-python", action="store_true", help="Print only the resolved interpreter path to stdout.")
    args = parser.parse_args()
    try:
        python = ensure_python(
            codex_home(args.codex_home),
            args.requirements.expanduser().resolve(),
            args.env_name,
            create=not args.no_create,
        )
        print(python)
        return 0
    except Exception as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
