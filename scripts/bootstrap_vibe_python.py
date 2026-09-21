#!/usr/bin/env python3
"""Create or repair the global Conda-backed Python environment for Vibe Coding.

An explicitly configured interpreter (``VIBE_PYTHON`` or ``CODEX_HOME/vibe-python``)
is never replaced silently. It is repaired in place when it is a Python 3.11+
interpreter that only lacks the Vibe requirements; otherwise the command fails with
an actionable message. Setting ``VIBE_PYTHON_REPAIR`` to an affirmative value
(``1``/``true``/``yes``/``on``) or passing ``--repair-interpreter`` opts in to
switching to the named Conda environment and rewriting the configuration file; any
other value (including ``0`` and ``false``) does not.
"""
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
PYTHON_ENV_NAME = "VIBE_PYTHON"
REPAIR_ENV_NAME = "VIBE_PYTHON_REPAIR"
AFFIRMATIVE = frozenset({"1", "true", "yes", "on"})


def repair_requested(flag: bool) -> bool:
    """Opt-in is explicit: the flag, or an affirmative environment value, and nothing else."""
    if flag:
        return True
    return os.environ.get(REPAIR_ENV_NAME, "").strip().lower() in AFFIRMATIVE


def codex_home(value: str | None) -> Path:
    raw = value or os.environ.get("CODEX_HOME")
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".codex").resolve()


def configured_python(home: Path) -> tuple[str | None, str | None, str | None]:
    """Return ``(interpreter, source, problem)`` for the configured interpreter.

    ``VIBE_PYTHON`` wins over the ``vibe-python`` file. Malformed values are reported
    through ``problem`` instead of raising, so the caller can offer a way out that
    actually works in the state that produced the error.
    """
    raw = os.environ.get(PYTHON_ENV_NAME, "")
    source = PYTHON_ENV_NAME if raw else None
    if source is None:
        path = home / PYTHON_CONFIG_NAME
        if path.is_file():
            source = str(path)
            raw = path.read_text(encoding="utf-8-sig")
            if not raw.strip():
                return None, source, f"Invalid interpreter configuration: {path} is empty"
    if source is None:
        return None, None, None
    value = raw.strip()
    candidate = Path(value) if value else None
    if (
        candidate is None
        or "\n" in value
        or "\r" in value
        or not candidate.is_absolute()
        or not candidate.is_file()
    ):
        return None, source, f"Configured Vibe Python must be one absolute executable path: {value!r}"
    return str(candidate.resolve()), source, None


def unusable_hint(source: str | None, home: Path, env_name: str) -> str:
    """The way out for a configured interpreter that cannot be used."""
    if source == PYTHON_ENV_NAME:
        return (
            f"Unset {PYTHON_ENV_NAME}, or point it at a Python 3.11+ interpreter with the Vibe "
            f"requirements installed."
        )
    return (
        f"Fix the path in {source or home / PYTHON_CONFIG_NAME}, or set {REPAIR_ENV_NAME}=1 to "
        f"switch to the Conda environment {env_name!r} and rewrite the configuration."
    )


def run(command: Sequence[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        list(command),
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=check,
    )


def probe(command: Sequence[str]) -> tuple[int, str]:
    """Run a diagnostic command without raising for a missing or unrunnable target.

    A manager shim or a stale configured path can name something that cannot be
    spawned at all. That is a normal outcome to report here, not a crash that leaks
    a raw ``FileNotFoundError`` to the user.
    """
    try:
        result = run(command, check=False)
    except OSError as error:
        return 127, str(error)
    return result.returncode, result.stdout or ""


def python_version_ok(python: str) -> tuple[bool, str]:
    """True when the executable is a Python 3.11+ interpreter, ignoring dependencies."""
    returncode, output = probe(
        [python, "-c", "import sys; assert sys.version_info >= (3, 11); print(sys.executable)"]
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if returncode == 0:
        return True, lines[-1] if lines else python
    return False, output.strip() or f"unable to run {python}"


def python_is_usable(python: str, requirements: Path) -> tuple[bool, str]:
    returncode, output = probe(
        [
            python,
            "-c",
            "import sys, yaml, jsonschema; "
            "assert sys.version_info >= (3, 11); "
            "print(sys.executable)",
        ]
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if returncode == 0:
        return True, lines[-1] if lines else python
    return False, output.strip() or f"unable to use {python}"


def find_conda() -> str | None:
    candidates = [
        os.environ.get("CONDA_EXE", ""),
        shutil.which("conda") or "",
        shutil.which("mamba") or "",
        str(Path.home() / "miniforge3/condabin/conda"),
        str(Path.home() / "mambaforge/condabin/conda"),
        str(Path.home() / "miniconda3/condabin/conda"),
    ]
    roots = [Path.home() / name for name in ("miniforge3", "mambaforge", "miniconda3", "anaconda3")]
    roots.extend(list(Path(sys.executable).resolve().parents)[:3])
    suffixes = ("condabin/conda.bat", "Scripts/conda.exe", "Library/bin/conda.bat") if os.name == "nt" else ("bin/conda", "condabin/conda")
    candidates.extend(str(base / suffix) for base in roots for suffix in suffixes)
    for raw in candidates:
        if raw and Path(raw).is_file() and os.access(raw, os.X_OK):
            return str(Path(raw).resolve())
    return None


def env_python(manager: str, env_name: str) -> tuple[str | None, str]:
    """Return ``(interpreter, manager output)`` for a Conda environment.

    A zero exit code is not evidence that the last printed line is an interpreter
    path: some manager shims print a ``CommandNotFoundError`` and still exit 0
    (reviewer-031 X3). The candidate must therefore name an existing file, otherwise
    the raw manager output is returned as the diagnostic instead of being handed to
    ``python_is_usable`` as if it were a path.
    """
    returncode, output = probe(
        [manager, "run", "-n", env_name, "python", "-c", "import sys; print(sys.executable)"]
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if returncode == 0 and lines and Path(lines[-1]).is_file():
        return lines[-1], output.strip()
    return None, output.strip()


def manager_diagnostic(manager: str, output: str) -> str:
    """Explain that the manager did not print an interpreter path, quoting its output."""
    text = output.strip()
    if not text:
        return f"\n{manager} printed no interpreter path for the environment."
    return f"\n{manager} did not print a usable interpreter path. Its output was:\n{text}"


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


def switch_interpreter(env_name: str, home: Path) -> None:
    """Announce an explicitly requested switch before the Conda environment is resolved."""
    print(
        f"[!] {REPAIR_ENV_NAME} is set; switching to Conda environment {env_name!r} and rewriting "
        f"{home / PYTHON_CONFIG_NAME}.",
        file=sys.stderr,
    )


def ensure_python(
    home: Path,
    requirements: Path,
    env_name: str,
    *,
    create: bool,
    repair_interpreter: bool = False,
) -> str:
    selected, source, problem = configured_python(home)
    if source is not None:
        if problem is not None:
            if not create:
                raise RuntimeError(problem)
            if not repair_interpreter or source == PYTHON_ENV_NAME:
                raise RuntimeError(f"{problem}\n{unusable_hint(source, home, env_name)}")
            switch_interpreter(env_name, home)
        else:
            usable, detail = python_is_usable(selected, requirements)
            if usable:
                return detail
            unusable = f"Configured Vibe Python is unusable: {selected}\n{detail}"
            if not create:
                raise RuntimeError(unusable)
            if repair_interpreter:
                if source == PYTHON_ENV_NAME:
                    raise RuntimeError(f"{unusable}\n{unusable_hint(source, home, env_name)}")
                switch_interpreter(env_name, home)
            else:
                version_ok, version_detail = python_version_ok(selected)
                if not version_ok:
                    raise RuntimeError(
                        f"Configured Vibe Python is not a Python 3.11+ interpreter: {selected}\n"
                        f"{version_detail}\n{unusable_hint(source, home, env_name)}"
                    )
                print(
                    f"[*] Installing the missing Vibe Python requirements into the configured interpreter {selected}.",
                    file=sys.stderr,
                )
                try:
                    install_requirements(selected, requirements)
                except RuntimeError as error:
                    raise RuntimeError(
                        f"Could not install the Vibe requirements into the configured interpreter {selected}: "
                        f"{error}\n{unusable_hint(source, home, env_name)}"
                    ) from error
                usable, detail = python_is_usable(selected, requirements)
                if usable:
                    return detail
                raise RuntimeError(
                    f"Configured Vibe Python remains unusable after installing the Vibe requirements: "
                    f"{selected}\n{detail}\n{unusable_hint(source, home, env_name)}"
                )

    manager = find_conda()
    if not manager:
        if source is not None:
            raise RuntimeError(
                f"Configured Vibe Python cannot be used ({source}) and no Conda/Miniforge executable was "
                f"found, so {REPAIR_ENV_NAME} cannot switch to the named environment."
            )
        raise RuntimeError(
            "No usable Vibe Python found. Install Miniforge/Miniconda or set VIBE_PYTHON to a Python 3.11+ environment."
        )

    python, manager_output = env_python(manager, env_name)
    if not python:
        if not create:
            raise RuntimeError(
                f"Conda environment {env_name!r} was not found; refusing to create it during uninstall."
                f"{manager_diagnostic(manager, manager_output)}"
            )
        create_env(manager, env_name)
        python, manager_output = env_python(manager, env_name)
    if not python:
        raise RuntimeError(
            f"Could not resolve Python from Conda environment {env_name!r}."
            f"{manager_diagnostic(manager, manager_output)}"
        )

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
    parser.add_argument(
        "--repair-interpreter",
        action="store_true",
        help="Opt in to replacing an unusable configured interpreter with the named Conda environment.",
    )
    parser.add_argument("--print-python", action="store_true", help="Print only the resolved interpreter path to stdout.")
    args = parser.parse_args()
    try:
        python = ensure_python(
            codex_home(args.codex_home),
            args.requirements.expanduser().resolve(),
            args.env_name,
            create=not args.no_create,
            repair_interpreter=repair_requested(args.repair_interpreter),
        )
        print(python)
        return 0
    except Exception as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
