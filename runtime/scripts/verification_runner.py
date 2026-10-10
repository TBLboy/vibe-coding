"""Controlled verification runner.

A reviewer's ability to verify must not rest on broad shell permission. This module is
the single entry point that runs project checks: every action is declared in a trusted
registry with structured argv, a fixed working directory, a scrubbed environment, a
timeout and a captured output digest. No model-authored command string is ever handed
to a shell, and an action outside the registry is refused rather than guessed at.

``preflight`` answers "can this action actually run here" *before* verification starts,
reporting ``verification_capability_missing`` instead of failing halfway through.
``run`` executes one trusted action and returns a traceable VerificationRun.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from state_store import StateError  # noqa: E402

COMMAND_SPEC_VERSION = 1

# The verification entry point must refuse an interpreter this runtime does not support.
# The reviewer's allowlist cannot be pinned to a POSIX-only wrapper (the installed
# `bin/vibe-python` is a shell script), so the version gate lives here instead: whatever
# interpreter a reviewer reaches for, an older one is a reported capability gap rather
# than a silent downgrade of the verification.
MINIMUM_PYTHON = (3, 11)

# The `hash` action needs a program rather than a test runner. It is a fixed script with
# the file list as argv, so a reviewer can re-derive a recorded digest without being
# handed a general-purpose shell: no flags, no command strings, no shell.
_HASH_SCRIPT = (
    "import hashlib, sys\n"
    "for path in sys.argv[1:]:\n"
    "    digest = hashlib.sha256()\n"
    "    with open(path, 'rb') as stream:\n"
    "        for block in iter(lambda: stream.read(1 << 20), b''):\n"
    "            digest.update(block)\n"
    "    print('%s  %s' % (digest.hexdigest(), path))\n"
)

# Every action is a fixed argv template plus the capability it needs. Nothing here
# accepts a caller-supplied command, flag or interpreter argument: a new check is added
# by declaring an action, not by widening a permission.
ACTION_SPECS = {
    "unittest": {
        "description": "discover and run the project's unittest suite",
        "requires_paths": ("tests",),
        "requires_modules": ("unittest",),
        "argument": None,
        "coverage": ("tests",),
    },
    "unittest-file": {
        "description": "run one unittest file from the project's tests directory",
        "requires_paths": ("tests",),
        "requires_modules": ("unittest",),
        "argument": "path",
        "coverage": ("tests",),
    },
    "pytest": {
        "description": "run the project's pytest suite",
        "requires_paths": ("tests",),
        "requires_modules": ("pytest",),
        "argument": None,
        "coverage": ("tests",),
    },
    "hash": {
        "description": "hash the bytes of named project files through the trusted entry point",
        "requires_paths": (),
        "requires_modules": (),
        "argument": "paths",
        "coverage": (),
    },
}

# A test process inherits only what it needs to start; everything else (tokens, proxy
# credentials, editor state) is dropped rather than passed through by default.
ENVIRONMENT_WHITELIST = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONHASHSEED", "LANG", "LC_ALL",
)

SHELL_METACHARACTERS = (";", "&", "|", "`", "$", "\n", "\r", ">", "<", "%", "!")


def action_ids() -> list[str]:
    """The trusted action names, sorted so callers can show a stable list."""
    return sorted(ACTION_SPECS)


def _spec(action: str) -> dict:
    if action not in ACTION_SPECS:
        raise StateError(
            "verification_action_untrusted",
            f"Untrusted verification action: {action!r}. Trusted actions: "
            + ", ".join(action_ids()),
        )
    return ACTION_SPECS[action]


def interpreter(python: str | None = None) -> str:
    """The interpreter an action runs with; defaults to the one running this module."""
    return python or sys.executable


def _environment() -> dict:
    whitelist = {name.upper() for name in ENVIRONMENT_WHITELIST}
    return {
        key: value for key, value in os.environ.items()
        if key.upper() in whitelist
    }


def _resolve_path(action: str, spec: dict, root: Path, path: str | None) -> str | None:
    """Resolve the optional file argument, keeping it inside the tests directory."""
    if spec["argument"] is None:
        if path is not None:
            raise StateError("invalid_input", f"Action {action!r} takes no path argument")
        return None
    if type(path) is not str or not path:
        raise StateError("invalid_input", f"Action {action!r} requires a path argument")
    if any(character in path for character in SHELL_METACHARACTERS):
        raise StateError(
            "invalid_input",
            f"Path argument must not contain shell metacharacters: {path!r}",
        )
    candidate = Path(path)
    if candidate.is_absolute():
        raise StateError(
            "invalid_input", f"Path argument must be relative to the project root: {path!r}"
        )
    tests = (root / "tests").resolve()
    resolved = (root / candidate).resolve()
    if resolved != tests and tests not in resolved.parents:
        raise StateError(
            "invalid_input", f"Path argument must stay inside tests/: {path!r}"
        )
    return candidate.as_posix()


def _resolve_paths(root: Path, paths) -> list[str]:
    """Resolve the file list for an action that hashes named files.

    Every path must stay inside the project and name an existing file, and the list is
    passed as argv rather than through a shell, so the action cannot be turned into a
    general-purpose command runner.
    """
    if type(paths) is not list or not paths:
        raise StateError("invalid_input", "This action requires a list of relative paths")
    base = Path(root).resolve()
    resolved: list[str] = []
    for path in paths:
        if type(path) is not str or not path:
            raise StateError("invalid_input", "Every hashed path must be a non-empty string")
        if any(character in path for character in SHELL_METACHARACTERS):
            raise StateError(
                "invalid_input",
                f"Path argument must not contain shell metacharacters: {path!r}",
            )
        candidate = Path(path)
        if candidate.is_absolute():
            raise StateError(
                "invalid_input", f"Path argument must be relative to the project root: {path!r}"
            )
        target = (base / candidate).resolve()
        if target != base and base not in target.parents:
            raise StateError(
                "invalid_input", f"Path argument must stay inside the project: {path!r}"
            )
        if not target.is_file():
            raise StateError("invalid_input", f"Path argument is not a file: {path!r}")
        resolved.append(candidate.as_posix())
    return resolved


def build_argv(action: str, root, path: str | None = None, python: str | None = None,
               paths=None) -> list[str]:
    """The exact argv for an action; callers never supply flags or a command string."""
    spec = _spec(action)
    root = Path(root)
    program = interpreter(python)
    if spec["argument"] == "paths":
        return [program, "-c", _HASH_SCRIPT] + _resolve_paths(root, paths)
    resolved = _resolve_path(action, spec, root, path)
    if action == "unittest":
        return [program, "-m", "unittest", "discover", "-s", "tests", "-q"]
    if action == "unittest-file":
        # `discover -p` matches its pattern against the *basename* (CPython's loader), so
        # passing the resolved relative path matched no file at all: the run exited 0
        # after `Ran 0 tests`, i.e. a targeted "pass" that executed nothing. `_resolve_path`
        # already confines the argument to `tests/`, so the basename is sufficient.
        return [program, "-m", "unittest", "discover", "-s", "tests", "-p",
                Path(resolved).name, "-q"]
    if action == "pytest":
        argv = [program, "-m", "pytest", "-q"]
        if resolved is not None:
            argv.append("tests/" + resolved)
        return argv
    raise StateError(
        "verification_action_untrusted", f"Untrusted verification action: {action!r}"
    )


_NO_TESTS_MARKER = "Ran 0 tests"


def _refuse_empty_run(action: str, output: str) -> None:
    """Treat a unittest run that executed nothing as a failure, not a pass.

    `unittest discover` exits 0 when its pattern matches no file, so a mis-resolved or
    mistyped target reads exactly like a green run. Targeted evidence is only evidence if
    it executed something, so a `Ran 0 tests` line is refused instead of recorded.
    """
    if action in ("unittest", "unittest-file") and _NO_TESTS_MARKER in output:
        raise StateError(
            "verification_no_tests",
            f"Action {action!r} ran 0 tests; a run that executes nothing is not evidence",
        )


def _interpreter_version(program: str, root: Path) -> tuple[int, int] | None:
    """The interpreter's major/minor version, or None when it cannot be probed."""
    probe = subprocess.run(
        [program, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
        cwd=str(root), env=_environment(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if probe.returncode != 0:
        return None
    parts = (probe.stdout or "").strip().split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1])


def _module_available(program: str, root: Path, module: str) -> bool:
    probe = subprocess.run(
        [program, "-c",
         "import importlib.util, sys; "
         f"sys.exit(0 if importlib.util.find_spec({module!r}) else 3)"],
        cwd=str(root), env=_environment(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    return probe.returncode == 0


def preflight(action: str, root, path: str | None = None, python: str | None = None,
              paths=None) -> dict:
    """Check whether an action can run here, before verification starts."""
    spec = _spec(action)
    root = Path(root).resolve()
    program = interpreter(python)
    checks: list[dict] = []
    missing: list[str] = []

    if os.sep in program or "/" in program:
        interpreter_ok = Path(program).is_file()
    else:
        interpreter_ok = shutil.which(program) is not None
    checks.append({"name": "interpreter", "ok": interpreter_ok, "detail": program})
    if not interpreter_ok:
        missing.append("interpreter")

    minimum = f"python>={MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}"
    version = _interpreter_version(program, root) if interpreter_ok else None
    version_ok = version is not None and version >= MINIMUM_PYTHON
    checks.append({
        "name": "interpreter-version",
        "ok": version_ok,
        "detail": (".".join(str(part) for part in version) if version
                   else f"could not probe {program}"),
    })
    if not version_ok:
        missing.append(minimum)

    for relative in spec["requires_paths"]:
        target = root / relative
        exists = target.exists()
        checks.append({"name": f"path:{relative}", "ok": exists, "detail": str(target)})
        if not exists:
            missing.append(relative)

    for module in spec["requires_modules"]:
        available = interpreter_ok and _module_available(program, root, module)
        checks.append({
            "name": f"module:{module}", "ok": available,
            "detail": f"{module} is {'importable' if available else 'not importable'}",
        })
        if not available:
            missing.append(module)

    # A bad argument is a caller error, not a missing capability: it propagates instead
    # of being folded into `verification_capability_missing`.
    argv = build_argv(action, root, path, program, paths)

    return {
        "action": action,
        "root": str(root),
        "available": not missing,
        "code": None if not missing else "verification_capability_missing",
        "missing": missing,
        "checks": checks,
        "argv": argv,
        "command_spec_version": COMMAND_SPEC_VERSION,
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(
    action: str, root, path: str | None = None, python: str | None = None,
    timeout: int = 900, paths=None,
) -> dict:
    """Execute one trusted action and return a traceable VerificationRun."""
    spec = _spec(action)
    root = Path(root).resolve()
    program = interpreter(python)
    report = preflight(action, root, path, program, paths)
    if not report["available"]:
        raise StateError(
            "verification_capability_missing",
            f"Action {action!r} cannot run here; missing: " + ", ".join(report["missing"]),
        )

    started = _timestamp()
    begin = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            report["argv"], cwd=str(root), env=_environment(), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=timeout,
        )
        exit_code = completed.returncode
        output = completed.stdout or ""
    except subprocess.TimeoutExpired as expired:
        exit_code = None
        timed_out = True
        captured = expired.stdout
        output = captured if isinstance(captured, str) else ""

    if not timed_out:
        _refuse_empty_run(action, output)

    coverage = list(spec["coverage"])
    if spec["argument"] == "path" and path:
        coverage = [f"tests/{Path(path).as_posix()}"]
    elif spec["argument"] == "paths" and paths:
        coverage = [Path(item).as_posix() for item in paths]
    return {
        "id": "VR-" + uuid.uuid4().hex[:16],
        "action_id": action,
        "command_spec_version": COMMAND_SPEC_VERSION,
        "cwd": str(root),
        "argv": report["argv"],
        "environment": {"python": program, "platform": platform.platform()},
        "started_at": started,
        "finished_at": _timestamp(),
        "duration_seconds": round(time.monotonic() - begin, 3),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "output_digest": hashlib.sha256(output.encode("utf-8", "replace")).hexdigest(),
        "output_bytes": len(output.encode("utf-8", "replace")),
        "output_tail": output[-4000:],
        "coverage_claims": {"paths": coverage},
        "limitations": [
            "runs inside the project worktree: a controlled entry point, not a sandbox",
            "the test process can still write files; the runner does not contain it",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="verification_runner",
        description="Run project checks through the trusted verification action registry.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        item = sub.add_parser(name)
        item.add_argument("--action", required=True, help="a trusted action id")
        item.add_argument("--root", default=".", help="project root (default: cwd)")
        item.add_argument("--path", help="file argument for actions that take one")
        item.add_argument("--paths", action="append",
                          help="project-relative file to hash (repeat for the hash action)")
        item.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)

    try:
        if args.command == "preflight":
            result = preflight(args.action, Path(args.root), args.path, paths=args.paths)
        else:
            result = run(args.action, Path(args.root), args.path, timeout=args.timeout,
                         paths=args.paths)
    except StateError as error:
        print(json.dumps(
            {"error": {"code": error.code, "message": str(error)}},
            ensure_ascii=False, sort_keys=True,
        ))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
