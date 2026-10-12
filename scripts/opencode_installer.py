#!/usr/bin/env python3
"""Install, update, verify, or remove the Vibe Coding OpenCode client surface."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable

RUNTIME_SCRIPTS = Path(__file__).resolve().parents[1] / "runtime" / "scripts"
if str(RUNTIME_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SCRIPTS))

from framework_info import VERSION  # noqa: E402


TITLE = "Vibe Coding - OpenCode Global Core"
PACKAGE_VERSION = VERSION
STATE_NAME = ".vibe-opencode-installation-state.json"
# OpenCode V2 loads a plugin *directory* whose default export is `{ id, setup }`. The
# installer places it under the config `plugins/` directory, where V2 discovers it on its
# own, so it is deliberately not listed in opencode.json: listing it as well loads it twice.
PLUGIN_RELATIVE = "plugins/vibe-workflow/index.ts"
# Specs older releases wrote for the V1 single-file plugin. V2 rejects them ("configured
# plugin path must be a directory"), so update and uninstall always drop them.
LEGACY_LOCAL_PLUGIN_SPECS = ("./plugins/vibe-workflow.ts",)
# The session Goal controller the global rules declare for OpenCode. It is pinned: the
# rule text names one version, so installing any other version would make the rule false.
# 0.1.60 is the first release that loads on OpenCode V2 (0.1.51 fails with
# "Schema.optionalWith is not a function" against the Effect v4 that V2 injects).
GOAL_PLUGIN_PACKAGE = "@prevalentware/opencode-goal-plugin"
GOAL_PLUGIN_VERSION = "0.1.60"
GOAL_PLUGIN_SPEC = f"{GOAL_PLUGIN_PACKAGE}@{GOAL_PLUGIN_VERSION}"
# Earlier pins of the same controller. An entry the installer itself wrote is migrated to
# the current pin on update; an entry the user owned is still reported as a conflict.
LEGACY_GOAL_PLUGIN_SPECS = (f"{GOAL_PLUGIN_PACKAGE}@0.1.51",)
MANAGED_PLUGIN_SPECS = (GOAL_PLUGIN_SPEC,)
AGENTS_RELATIVE = "AGENTS.md"
AGENTS_BEGIN = "<!-- VIBE-OPENCODE-GLOBAL:BEGIN -->"
AGENTS_END = "<!-- VIBE-OPENCODE-GLOBAL:END -->"
# Older releases installed this npm package for the V1 plugin API. V2 provides the plugin
# API (`@opencode/plugin`) itself, so the dependency is no longer installed; an update
# removes the entry an older release added to package.json.
LEGACY_OPENCODE_PACKAGE = "@opencode-ai/plugin"
# Only OpenCode V2 is supported (V1 plugin API and single-file plugins are not maintained).
MIN_OPENCODE_MAJOR = 2
# CLI shipped inside the desktop application, used when `opencode` is not on PATH.
DESKTOP_CLI_CANDIDATES = ("/opt/OpenCode/resources/opencode-cli",)
EXCLUDED_NAMES = {"__pycache__", "node_modules"}
ASSET_DIRECTORIES = ("agents", "bin", "commands", "plugins")
SKILLS_RELATIVE = "skills"
RUNTIME_RELATIVE = "vibe-workflow"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_dir(value: str | None) -> Path:
    raw = value or os.environ.get("OPENCODE_CONFIG_DIR")
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".config" / "opencode").resolve()


def state_path(home: Path) -> Path:
    return destination_for(home, STATE_NAME)


def norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise RuntimeError(f"invalid JSON in {path}: {error}") from error


def read_state(home: Path) -> dict[str, Any]:
    value = read_json(state_path(home), {})
    if not isinstance(value, dict):
        return {}
    return heal_state(value)


def heal_state(state: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy host-separator keys so an older state file keeps working.

    Reading tolerates the historical spelling and the next write persists the POSIX
    form, so an existing installation migrates instead of reporting false conflicts.
    The number of rewritten keys is reported on ``legacy_separator_keys`` so the
    caller can tell the user a migration happened.
    """
    rewritten = 0

    def heal(value: Any) -> Any:
        nonlocal rewritten
        if not isinstance(value, str):
            return value
        canonical = canonical_relative(value)
        if canonical is None or canonical == value:
            return value
        rewritten += 1
        return canonical

    managed = state.get("managed_files")
    if isinstance(managed, dict):
        state["managed_files"] = {heal(key): digest for key, digest in managed.items()}
    preserved = state.get("preserved_local")
    if isinstance(preserved, list):
        state["preserved_local"] = [heal(item) for item in preserved]
    created = state.get("created_dirs")
    if isinstance(created, list):
        state["created_dirs"] = [heal(item) for item in created]
    if rewritten:
        state["legacy_separator_keys"] = rewritten
    return state


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_assets(root: Path) -> dict[str, Path]:
    surface = root / "runtime" / "opencode"
    # NOTE: two surface files are deliberately NOT generic managed assets:
    #   * AGENTS.md is merged as a marker block so user rules are preserved.
    #   * opencode.json is merged by merge_config() and selectively restored by
    #     remove_managed_config(); copying it wholesale would clobber user
    #     plugin/permission/model/mcp settings and delete the file on uninstall.
    assets: dict[str, Path] = {}
    for directory in ASSET_DIRECTORIES:
        for path in sorted((surface / directory).rglob("*")):
            if path.is_file() and not any(part in EXCLUDED_NAMES for part in path.parts):
                assets[path.relative_to(surface).as_posix()] = path
    skills = root / SKILLS_RELATIVE
    for path in sorted(skills.glob("*/SKILL.md")):
        assets[path.relative_to(root).as_posix()] = path
        for extra in sorted(path.parent.rglob("*")):
            if extra.is_file() and not any(part in EXCLUDED_NAMES for part in extra.parts):
                assets[extra.relative_to(root).as_posix()] = extra
    return assets


def runtime_assets(root: Path) -> dict[str, Path]:
    runtime = root / "runtime"
    assets: dict[str, Path] = {}
    for path in sorted(runtime.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(runtime)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] == "opencode":
            continue
        assets[relative.as_posix()] = path
    return assets


def safe_relative(relative: Any) -> str | None:
    """Return a normalized relative POSIX path, or None when it escapes the home."""
    if not isinstance(relative, str) or not relative.strip():
        return None
    candidate = Path(relative)
    if candidate.is_absolute():
        return None
    parts = [part for part in candidate.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return Path(*parts).as_posix()


def canonical_relative(relative: Any) -> str | None:
    """Return the POSIX contract form of a recorded relative path, or None.

    The installation state is a cross-platform contract whose ``managed_files``,
    ``preserved_local`` and ``created_dirs`` keys are POSIX relative paths. Older
    builds recorded the host separator instead, which is not portable: on POSIX a
    backslash is an ordinary file-name character, so ``agents\\x.md`` would name a
    different file. A recorded backslash is therefore always a legacy separator and
    is converted before the safety check, on every platform.
    """
    if not isinstance(relative, str):
        return None
    return safe_relative(relative.replace("\\", "/"))


def destination_for(home: Path, relative: str) -> Path:
    safe = canonical_relative(relative)
    if safe is None:
        raise RuntimeError(f"unsafe installation path in installation state: {relative!r}")
    target = home / safe
    # A planted symlink inside the home must not redirect writes or deletes outside it.
    try:
        target.resolve().relative_to(home.resolve())
    except ValueError:
        raise RuntimeError(f"refusing to touch a path outside the OpenCode home: {target}") from None
    return target


def source_agents(root: Path) -> str:
    path = root / "runtime" / "opencode" / AGENTS_RELATIVE
    if not path.is_file():
        raise RuntimeError(f"package is missing runtime/opencode/{AGENTS_RELATIVE}")
    return path.read_text(encoding="utf-8").rstrip()


def agents_block(root: Path) -> str:
    return f"{AGENTS_BEGIN}\n{source_agents(root)}\n{AGENTS_END}"


def install_agents_block(root: Path, home: Path) -> None:
    agents = destination_for(home, AGENTS_RELATIVE)
    old = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    block = agents_block(root)
    begins = old.count(AGENTS_BEGIN)
    ends = old.count(AGENTS_END)
    if begins == 0 and ends == 0:
        merged = old.rstrip() + ("\n\n" if old.rstrip() else "") + block + "\n"
    elif begins == 1 and ends == 1 and old.index(AGENTS_BEGIN) < old.index(AGENTS_END):
        start = old.index(AGENTS_BEGIN)
        end = old.index(AGENTS_END) + len(AGENTS_END)
        merged = old[:start] + block + old[end:]
    else:
        raise RuntimeError(
            f"{AGENTS_RELATIVE} has a damaged managed block "
            f"({begins} BEGIN / {ends} END markers); refusing to rewrite it"
        )
    agents.write_text(merged, encoding="utf-8", newline="\n")


def remove_agents_block(home: Path) -> None:
    agents = destination_for(home, AGENTS_RELATIVE)
    if not agents.is_file():
        return
    old = agents.read_text(encoding="utf-8")
    begins = old.count(AGENTS_BEGIN)
    ends = old.count(AGENTS_END)
    if begins == 0 and ends == 0:
        return
    if begins != 1 or ends != 1:
        raise RuntimeError(
            f"{AGENTS_RELATIVE} has a damaged managed block "
            f"({begins} BEGIN / {ends} END markers); refusing to modify it"
        )
    start = old.index(AGENTS_BEGIN)
    end = old.index(AGENTS_END)
    if end < start:
        raise RuntimeError(f"{AGENTS_RELATIVE} managed block markers are out of order; refusing to modify it")
    remaining = (old[:start] + old[end + len(AGENTS_END) :]).strip()
    if remaining:
        agents.write_text(remaining + "\n", encoding="utf-8", newline="\n")
    else:
        agents.unlink()


def agents_block_present(root: Path, home: Path) -> bool:
    agents = destination_for(home, AGENTS_RELATIVE)
    if not agents.is_file():
        return False
    return agents_block(root) in agents.read_text(encoding="utf-8")


def agents_block_consistent(home: Path) -> bool:
    """True when AGENTS.md has no managed block or exactly one well-formed block."""
    agents = destination_for(home, AGENTS_RELATIVE)
    if not agents.is_file():
        return True
    text = agents.read_text(encoding="utf-8")
    begins = text.count(AGENTS_BEGIN)
    ends = text.count(AGENTS_END)
    if begins == 0 and ends == 0:
        return True
    return begins == 1 and ends == 1 and text.index(AGENTS_BEGIN) < text.index(AGENTS_END)


def snapshot_paths(home: Path, relatives: Iterable[str]) -> dict[str, bytes | None]:
    snapshot: dict[str, bytes | None] = {}
    for relative in relatives:
        path = destination_for(home, relative)
        snapshot[relative] = path.read_bytes() if path.is_file() else None
    return snapshot


def restore_snapshot(home: Path, snapshot: dict[str, bytes | None]) -> None:
    for relative, data in snapshot.items():
        path = destination_for(home, relative)
        if data is None:
            if path.is_file():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def validate_existing_json(home: Path) -> None:
    """Fail before any write/delete when a config we must edit is not valid JSON."""
    for name in ("opencode.json", "package.json"):
        path = destination_for(home, name)
        if path.is_file():
            read_json(path, None)


def tracked_relatives(root: Path) -> list[str]:
    return [
        *managed_sources(root).keys(),
        AGENTS_RELATIVE,
        "opencode.json",
        "package.json",
        "vibe-python",
        STATE_NAME,
    ]


def missing_dirs(home: Path, relatives: Iterable[str]) -> list[str]:
    """Directories the install will create, recorded exactly (not just top level)."""
    missing: set[str] = set()
    for relative in relatives:
        parts = Path(relative).parts[:-1]
        for depth in range(1, len(parts) + 1):
            candidate = Path(*parts[:depth]).as_posix()
            if not (home / candidate).exists():
                missing.add(candidate)
    return sorted(missing)


# No package manager runs any more (OpenCode V2 provides the plugin API), but configs
# installed by older releases still carry these artifacts, and the user's own tooling may
# write them; snapshotting them keeps rollback byte-exact and refuses escaping symlinks.
LOCKFILES = ("package-lock.json", "bun.lock", "bun.lockb", "yarn.lock", "pnpm-lock.yaml")
PACKAGE_ARTIFACTS = ("node_modules", *LOCKFILES)


def transaction_snapshot(home: Path, relatives: Iterable[str]) -> dict[str, Any]:
    created_artifacts: list[str] = []
    for name in PACKAGE_ARTIFACTS:
        # Resolve first: an escaping symlink must abort the run before the package
        # manager can write through it.
        if not destination_for(home, name).exists():
            created_artifacts.append(name)
    return {
        "files": snapshot_paths(home, relatives),
        "created_dirs": missing_dirs(home, relatives),
        "created_artifacts": created_artifacts,
        "lockfiles": {
            name: destination_for(home, name).read_bytes()
            for name in LOCKFILES
            if destination_for(home, name).is_file()
        },
    }


def rollback_transaction(home: Path, snapshot: dict[str, Any]) -> None:
    restore_snapshot(home, snapshot.get("files") or {})
    for name, data in (snapshot.get("lockfiles") or {}).items():
        destination_for(home, name).write_bytes(data)
    for name in snapshot.get("created_artifacts") or []:
        target = destination_for(home, name)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.is_file():
            target.unlink()
    for relative in sorted(snapshot.get("created_dirs") or [], key=lambda p: p.count("/"), reverse=True):
        target = destination_for(home, relative)
        if target.is_dir():
            try:
                target.rmdir()
            except OSError:
                pass


def validate_state_shape(state: dict[str, Any]) -> None:
    managed = state.get("managed_files")
    if managed is not None:
        if not isinstance(managed, dict):
            raise RuntimeError("installation state field 'managed_files' is malformed")
        for relative, digest in managed.items():
            if canonical_relative(relative) is None:
                raise RuntimeError(f"installation state has an unsafe managed path: {relative!r}")
            if not isinstance(digest, str):
                raise RuntimeError(f"installation state has a non-string hash for {relative!r}")
    permissions = state.get("permissions_added")
    if permissions is not None and not isinstance(permissions, dict):
        raise RuntimeError("installation state field 'permissions_added' is malformed")
    created = state.get("created_dirs")
    if created is not None and not (
        isinstance(created, list) and all(isinstance(item, str) for item in created)
    ):
        raise RuntimeError("installation state field 'created_dirs' is malformed")
    for relative in created or []:
        if canonical_relative(relative) is None:
            raise RuntimeError(f"installation state has an unsafe directory path: {relative!r}")


def assert_canonical_state(state: dict[str, Any]) -> None:
    """Refuse to persist a state file whose keys are not in the POSIX contract form.

    Reading tolerates legacy host-separator keys because they are normalized on
    read, but writing must never reintroduce them: a Windows-only spelling is not
    portable and would name a different file on a POSIX host. A regression here is a
    loud error rather than a silently malformed installation state.
    """
    fields: list[tuple[str, Iterable[Any]]] = []
    for name in ("managed_files", "preserved_local", "created_dirs"):
        value = state.get(name)
        if isinstance(value, dict):
            fields.append((name, value.keys()))
        elif isinstance(value, list):
            fields.append((name, value))
    for name, keys in fields:
        for key in keys:
            canonical = canonical_relative(key)
            if canonical is None or canonical != key:
                raise RuntimeError(
                    "refusing to write a non-POSIX relative path into installation "
                    f"state field {name!r}: {key!r}"
                )


def plan_sync(
    home: Path,
    sources: dict[str, Path],
    previous: dict[str, str],
) -> tuple[list[tuple[str, str]], list[str], list[str], dict[str, str]]:
    """Decide copy/remove operations and surface conflicts before any write.

    Mirrors the uninstall semantics of the rest of the installer: a file that already exists and does
    not match the package is a hard conflict, never a silent overwrite.
    """
    operations: list[tuple[str, str]] = []
    conflicts: list[str] = []
    preserved: list[str] = []
    managed: dict[str, str] = {}
    # A caller may hand us a state that predates the POSIX key contract. Compare on
    # the contract form so legacy keys migrate instead of looking like brand-new
    # files (which would be reported as a pre-existing conflict).
    previous = {(canonical_relative(key) or key): digest for key, digest in previous.items()}
    for key, source in sources.items():
        destination = destination_for(home, key)
        current_hash = sha256_file(destination) if destination.is_file() else None
        source_hash = sha256_file(source)
        previous_hash = previous.get(key)
        if current_hash is None:
            operations.append(("copy", key))
            managed[key] = source_hash
        elif previous_hash is None:
            if current_hash == source_hash:
                managed[key] = source_hash
            else:
                conflicts.append(f"{key}: pre-existing file differs from package")
        elif current_hash == previous_hash:
            if source_hash != current_hash:
                operations.append(("copy", key))
            managed[key] = source_hash
        elif source_hash == previous_hash:
            preserved.append(key)
            managed[key] = previous_hash
        else:
            conflicts.append(f"{key}: local and package versions both changed")
            managed[key] = previous_hash
    for key, previous_hash in previous.items():
        if key in sources or key == "vibe-python":
            continue
        destination = destination_for(home, key)
        if not destination.exists():
            continue
        if destination.is_file() and sha256_file(destination) == previous_hash:
            operations.append(("remove", key))
        else:
            conflicts.append(f"{key}: removed by package but locally modified")
            preserved.append(key)
            managed[key] = previous_hash
    return operations, conflicts, preserved, managed


def apply_sync(home: Path, sources: dict[str, Path], operations: list[tuple[str, str]]) -> None:
    for action, key in operations:
        destination = destination_for(home, key)
        if action == "copy":
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sources[key], destination)
        elif action == "remove" and destination.is_file():
            destination.unlink()


def validate_source(root: Path) -> None:
    missing = [
        relative for relative, path in source_assets(root).items() if not path.is_file()
    ]
    if missing:
        raise RuntimeError("package is missing OpenCode assets: " + ", ".join(missing))
    for relative in (AGENTS_RELATIVE, "opencode.json"):
        if not (root / "runtime" / "opencode" / relative).is_file():
            raise RuntimeError(f"package is missing runtime/opencode/{relative}")
    config = read_json(root / "runtime" / "opencode" / "opencode.json", {})
    if not isinstance(config, dict) or config.get("default_agent") != "vibe-main":
        raise RuntimeError("runtime/opencode/opencode.json must set default_agent to vibe-main")
    for required in ("scripts/vibe.py", "project-log-template"):
        if not (root / "runtime" / required).exists():
            raise RuntimeError(f"runtime/{required} is required for the OpenCode installation")


def detect_python(root: Path, home: Path) -> str:
    candidates: list[str] = []
    configured = destination_for(home, "vibe-python")
    if configured.is_file():
        candidates.append(configured.read_text(encoding="utf-8").strip())
    env_pointer = os.environ.get("VIBE_PYTHON", "").strip()
    if env_pointer:
        candidates.append(env_pointer)
    if sys.executable:
        candidates.append(sys.executable)
    candidates.extend(["python3", "python"])
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isabs(candidate):
            resolved = candidate if os.path.isfile(candidate) and os.access(candidate, os.X_OK) else None
        else:
            resolved = shutil.which(candidate)
        if not resolved:
            continue
        try:
            probe = subprocess.run(
                [resolved, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
        except OSError:
            continue
        if probe.returncode == 0:
            return resolved
    raise RuntimeError("Python 3.11+ is required for the Vibe runtime")


def detect_opencode() -> str | None:
    return shutil.which("opencode")


def detect_desktop_cli() -> str | None:
    """CLI bundled with the desktop application, when `opencode` itself is not on PATH."""
    for candidate in DESKTOP_CLI_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def opencode_version(executable: str) -> str | None:
    """Return the ``X.Y.Z`` version an OpenCode CLI reports, or None when it cannot tell."""
    try:
        result = subprocess.run(
            [executable, "--version"], text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout or "")
    return ".".join(match.groups()) if match else None


def preflight(root: Path, home: Path, *, skip_plugin_install: bool = False) -> dict[str, Any]:
    """Probe the host before writing anything.

    ``skip_plugin_install`` is accepted for compatibility with older callers; OpenCode V2
    provides the plugin API itself, so there is no npm dependency left to install.
    """
    del skip_plugin_install
    validate_source(root)
    warnings: list[str] = []
    opencode = detect_opencode()
    version: str | None = None
    if opencode:
        version = opencode_version(opencode)
    else:
        desktop = detect_desktop_cli()
        if desktop:
            version = opencode_version(desktop)
            warnings.append(
                f"opencode is not on PATH, but the desktop application ships a CLI at {desktop}; "
                f"link it to use the workflow from a shell: ln -sf {desktop} ~/.local/bin/opencode"
            )
        else:
            warnings.append("opencode CLI was not found on PATH; install OpenCode V2 before using the workflow")
    if (opencode or detect_desktop_cli()) and version is None:
        warnings.append(
            "could not read the OpenCode version; this package supports OpenCode "
            f"{MIN_OPENCODE_MAJOR}.x only, so confirm `opencode --version` reports 2.x"
        )
    if version is not None and int(version.split(".")[0]) < MIN_OPENCODE_MAJOR:
        raise RuntimeError(
            f"OpenCode {version} is a V1 release; this package supports OpenCode "
            f"{MIN_OPENCODE_MAJOR}.x only (V1 plugin API is not maintained). Upgrade OpenCode first."
        )
    if os.environ.get("PYTHONPATH"):
        warnings.append(
            "PYTHONPATH is set; it can shadow the Vibe runtime dependencies with another "
            "Python's packages. The workflow plugin drops it for runtime calls; unset it "
            "when running vibe.py by hand."
        )
    return {
        "python": detect_python(root, home),
        "opencode": opencode,
        "opencode_version": version,
        "config_dir": str(home),
        "warnings": warnings,
    }


def backup(home: Path, action: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = destination_for(home, "backups") / f"{action}-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for relative in ("AGENTS.md", "opencode.json", "vibe-workflow", "vibe-python", *ASSET_DIRECTORIES):
        source = destination_for(home, relative)
        if source.is_file():
            target = backup_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif source.is_dir():
            shutil.copytree(source, backup_dir / relative, dirs_exist_ok=True)
    skills = destination_for(home, SKILLS_RELATIVE)
    if skills.is_dir():
        shutil.copytree(skills, backup_dir / SKILLS_RELATIVE, dirs_exist_ok=True)
    return backup_dir


def managed_sources(root: Path) -> dict[str, Path]:
    sources: dict[str, Path] = dict(source_assets(root))
    for relative, source in runtime_assets(root).items():
        sources[f"{RUNTIME_RELATIVE}/{relative}"] = source
    return sources


def plugin_key(item: Any) -> str:
    return json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)


def plugin_package_name(spec: Any) -> str | None:
    """Registry package name of a plugin spec, or None for local/path specs.

    ``@scope/name@1.2.3``, ``@scope/name`` and ``@scope/name@latest`` all name the same
    package, so ownership and conflict checks must not depend on the exact string.
    Surrounding whitespace and letter case are normalised away as well: a user entry
    spelled ``@Scope/Name`` must still be recognised as the same package as
    ``@scope/name``, which is what makes the conflict guard reliable.
    """
    if not isinstance(spec, str):
        return None
    spec = spec.strip()
    if not spec or spec.startswith((".", "/", "file:")):
        return None
    scoped = spec.startswith("@")
    body = spec[1:] if scoped else spec
    name, _, _version = body.rpartition("@")
    name = (name or body).lower()
    return f"@{name}" if scoped else name


def configured_plugins(config: Any) -> list[Any]:
    """Every plugin entry in a config, across the V2 `plugins` and older `plugin` keys."""
    if not isinstance(config, dict):
        return []
    entries: list[Any] = []
    for key in ("plugins", "plugin"):
        value = config.get(key)
        if isinstance(value, list):
            entries.extend(value)
    return entries


def plugin_list_key(config: dict[str, Any]) -> str:
    """The plugin list key a config uses: V2 `plugins`, or the older `plugin` it normalizes."""
    if "plugins" in config:
        return "plugins"
    return "plugin"


def dedupe_plugins(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    ordered: list[Any] = []
    for item in items:
        key = plugin_key(item)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def merge_config(home: Path, root: Path, previous_ownership: Any) -> dict[str, Any]:
    """Merge managed keys into the user config, preserving everything else.

    Returns the ownership record so uninstall can restore exactly what the user
    had before the installer touched the file.
    """
    config_path = destination_for(home, "opencode.json")
    existing = read_json(config_path, {})
    if existing is None:
        existing = {}
    if not isinstance(existing, dict):
        raise RuntimeError(f"{config_path} must contain a JSON object")
    source = read_json(root / "runtime" / "opencode" / "opencode.json", {})
    previous = previous_ownership if isinstance(previous_ownership, dict) else {}
    ownership: dict[str, Any] = {}
    notes: list[str] = []

    merged = dict(existing)
    schema_ownership = previous.get("schema")
    source_schema = source.get("$schema")
    if not isinstance(schema_ownership, dict) or "present" not in schema_ownership:
        schema_ownership = (
            {"present": True, "previous": existing["$schema"]}
            if "$schema" in existing
            else {"present": False, "installed": source_schema}
        )
    elif not schema_ownership.get("present"):
        recorded_schema = schema_ownership.get("installed")
        current_schema = existing.get("$schema")
        if current_schema is None and recorded_schema is not None:
            # The user deleted the schema line the installer wrote.
            schema_ownership = {"present": True, "previous": None}
        elif current_schema is not None and current_schema != recorded_schema:
            # The user edited it; hand ownership back and never overwrite it.
            schema_ownership = {"present": True, "previous": current_schema}
    ownership["schema"] = schema_ownership
    if not schema_ownership.get("present") and source_schema is not None:
        merged["$schema"] = source_schema
    file_created = previous.get("file_created")
    ownership["file_created"] = file_created if isinstance(file_created, bool) else not config_path.is_file()

    # --- default_agent -----------------------------------------------------
    agent_ownership = previous.get("default_agent")
    if not isinstance(agent_ownership, dict) or "present" not in agent_ownership:
        agent_ownership = (
            {"present": True, "previous": existing["default_agent"]}
            if "default_agent" in existing
            else {"present": False}
        )
    ownership["default_agent"] = agent_ownership
    merged["default_agent"] = source.get("default_agent", "vibe-main")

    # --- plugin registration ----------------------------------------------
    # V2 names the list `plugins`; it still normalizes the older `plugin` key, and a
    # config may carry both. Every check below runs across both lists; the managed spec
    # is written to the primary one (`plugins` when present) and removed from the other.
    list_key = plugin_list_key(existing)
    lists: dict[str, list[Any]] = {}
    for key_name in ("plugins", "plugin"):
        if key_name not in existing and key_name != list_key:
            continue
        value = existing.get(key_name)
        if value is None:
            value = []
        if not isinstance(value, list):
            raise RuntimeError(f"opencode.json {key_name} must be a list")
        lists[key_name] = list(value)
    ownership["plugin_list_key"] = list_key

    def all_plugins() -> list[Any]:
        return [item for entries in lists.values() for item in entries]

    def drop(keys: set[str]) -> None:
        for key_name in lists:
            lists[key_name] = [item for item in lists[key_name] if plugin_key(item) not in keys]

    legacy_local = {plugin_key(spec) for spec in LEGACY_LOCAL_PLUGIN_SPECS}
    dropped_local = [item for item in all_plugins() if plugin_key(item) in legacy_local]
    if dropped_local:
        notes.append(
            "removed the V1 single-file plugin registration "
            + ", ".join(repr(item) for item in dropped_local)
            + "; OpenCode V2 discovers plugins/vibe-workflow/ on its own"
        )
    drop(legacy_local)
    # Third-party specs the installer registers on the user's behalf, each recorded with
    # whether the user already had it so uninstall removes only what the installer added.
    plugins_added = previous.get("plugins_added")
    if not isinstance(plugins_added, dict):
        plugins_added = {}
    # Migrate older pins of the Goal controller that the installer itself wrote.
    for legacy in LEGACY_GOAL_PLUGIN_SPECS:
        key = plugin_key(legacy)
        if key in plugins_added and not plugins_added[key]:
            if any(plugin_key(item) == key for item in all_plugins()):
                notes.append(f"migrated the session Goal controller {legacy!r} to {GOAL_PLUGIN_SPEC!r}")
            drop({key})
            plugins_added = {
                **{k: v for k, v in plugins_added.items() if k != key},
                plugin_key(GOAL_PLUGIN_SPEC): False,
            }
    managed_ownership: dict[str, bool] = {}
    managed_keys = {plugin_key(spec) for spec in MANAGED_PLUGIN_SPECS}
    for spec in MANAGED_PLUGIN_SPECS:
        key = plugin_key(spec)
        if key in plugins_added:
            managed_ownership[key] = bool(plugins_added[key])
        else:
            managed_ownership[key] = any(
                plugin_package_name(item) == plugin_package_name(spec) for item in all_plugins()
            )
    ownership["plugins_added"] = managed_ownership
    # The global rules name one version, so a second entry for the same package would make
    # the rule ambiguous and could double-register the controller. Refuse instead.
    for spec in MANAGED_PLUGIN_SPECS:
        name = plugin_package_name(spec)
        conflicts = [
            item for item in all_plugins()
            if plugin_package_name(item) == name and plugin_key(item) != plugin_key(spec)
        ]
        if conflicts:
            raise RuntimeError(
                f"opencode.json already registers {name} as {conflicts[0]!r}, but this "
                f"package pins {spec!r}. Remove or align that entry first: the session Goal "
                "controller version is declared by the global rules, so two versions would "
                "be ambiguous."
            )
    drop(managed_keys)
    lists[list_key] = dedupe_plugins([*lists[list_key], *MANAGED_PLUGIN_SPECS])
    for key_name, entries in lists.items():
        merged[key_name] = entries

    # --- managed permission rules -----------------------------------------
    permissions = dict(existing.get("permission")) if isinstance(existing.get("permission"), dict) else {}
    source_permission = source.get("permission") if isinstance(source.get("permission"), dict) else {}
    previous_permissions = previous.get("permissions_added")
    if not isinstance(previous_permissions, dict):
        previous_permissions = {}
    permissions_ownership: dict[str, dict[str, Any]] = {}
    # Iterate the union so rules the package stopped shipping keep their ownership
    # instead of being silently orphaned in the user config.
    for group in sorted(set(source_permission) | set(previous_permissions)):
        rules = source_permission.get(group)
        if not isinstance(rules, dict):
            rules = {}
        recorded = previous_permissions.get(group)
        if not isinstance(recorded, dict):
            recorded = {}
        current = permissions.get(group)
        merged_rules = dict(current) if isinstance(current, dict) else {}
        group_ownership: dict[str, Any] = {}
        for pattern in sorted(set(rules) | set(recorded)):
            action = rules.get(pattern)
            info = recorded.get(pattern)
            owned = isinstance(info, dict) and "present" in info and not info.get("present")
            if action is None:
                # The package no longer ships this rule.
                if not owned:
                    continue
                if pattern in merged_rules and merged_rules[pattern] != info.get("installed"):
                    group_ownership[pattern] = {"present": True, "previous": merged_rules[pattern]}
                else:
                    merged_rules.pop(pattern, None)
                continue
            if not isinstance(info, dict) or "present" not in info:
                if pattern in merged_rules:
                    group_ownership[pattern] = {
                        "present": True, "previous": merged_rules[pattern], "installed": action,
                    }
                else:
                    merged_rules[pattern] = action
                    group_ownership[pattern] = {"present": False, "installed": action}
            elif info.get("present"):
                # The value predates the installer; never overwrite the user's own rule.
                group_ownership[pattern] = info
            else:
                installed = info.get("installed")
                if pattern not in merged_rules:
                    # The user deleted a rule the installer owns; respect the deletion.
                    notes.append(
                        f"permission.{group}.{pattern}: managed rule removed by the user; not restoring it"
                    )
                    continue
                if installed is not None and merged_rules[pattern] != installed:
                    # The user edited a rule the installer owns; hand ownership back to them.
                    group_ownership[pattern] = {
                        "present": True, "previous": merged_rules[pattern], "installed": action,
                    }
                else:
                    merged_rules[pattern] = action
                    group_ownership[pattern] = {"present": False, "installed": action}
        if merged_rules:
            permissions[group] = merged_rules
        else:
            permissions.pop(group, None)
        if group_ownership:
            permissions_ownership[group] = group_ownership
    if permissions:
        merged["permission"] = permissions
    else:
        merged.pop("permission", None)
    ownership["permissions_added"] = permissions_ownership
    ownership["notes"] = notes
    write_json(config_path, merged)
    return ownership


def restore_package_json(home: Path, ownership: Any) -> None:
    info = ownership if isinstance(ownership, dict) else {}
    if not info:
        return
    package_json = destination_for(home, "package.json")
    if not package_json.is_file():
        return
    package = read_json(package_json, {})
    if not isinstance(package, dict):
        return
    dependencies = package.get("dependencies")
    if not isinstance(dependencies, dict):
        dependencies = {}
    previous_dependency = info.get("previous_dependency")
    if previous_dependency is None:
        dependencies.pop(LEGACY_OPENCODE_PACKAGE, None)
    else:
        dependencies[LEGACY_OPENCODE_PACKAGE] = previous_dependency
    if dependencies:
        package["dependencies"] = dependencies
    else:
        package.pop("dependencies", None)
    if not info.get("existed") and not package:
        package_json.unlink()
        return
    write_json(package_json, package)


def install_or_update(
    root: Path,
    home: Path,
    *,
    skip_preflight: bool,
    skip_plugin_install: bool,
) -> None:
    home.mkdir(parents=True, exist_ok=True)
    old_state = read_state(home)
    previous_managed = old_state.get("managed_files", {})
    if not isinstance(previous_managed, dict):
        previous_managed = {}
    del skip_plugin_install  # accepted for compatibility; V2 has no npm dependency to install
    probe = old_state.get("preflight") if skip_preflight else preflight(root, home)
    if not isinstance(probe, dict):
        probe = {}

    sources = managed_sources(root)
    operations, conflicts, preserved, managed = plan_sync(home, sources, previous_managed)
    if conflicts:
        raise RuntimeError(
            "OpenCode installation conflicts detected before writing:\n- "
            + "\n- ".join(conflicts)
            + "\nMove or remove the listed files, then rerun. Nothing was written."
        )
    validate_existing_json(home)
    if not agents_block_consistent(home):
        raise RuntimeError(
            f"{AGENTS_RELATIVE} has a damaged managed block; refusing to rewrite it. Nothing was written."
        )

    validate_state_shape(old_state)
    snapshot = transaction_snapshot(home, tracked_relatives(root))
    created_dirs = sorted(set(old_state.get("created_dirs") or []) | set(snapshot["created_dirs"]))
    backup_dir = backup(home, "update" if old_state else "install")
    try:
        config_ownership = merge_config(home, root, old_state.get("opencode_config", {}))
        install_agents_block(root, home)
        apply_sync(home, sources, operations)

        python = probe.get("python") or detect_python(root, home)
        python_pointer = destination_for(home, "vibe-python")
        desired_pointer = f"{python}\n"
        previous_pointer_hash = previous_managed.get("vibe-python")
        if (
            python_pointer.is_file()
            and python_pointer.read_text(encoding="utf-8") != desired_pointer
            and previous_pointer_hash is not None
            and sha256_file(python_pointer) != previous_pointer_hash
        ):
            preserved.append("vibe-python")
            managed["vibe-python"] = previous_pointer_hash
        else:
            python_pointer.write_text(desired_pointer, encoding="utf-8")
            managed["vibe-python"] = sha256_file(python_pointer)

        # OpenCode V2 provides the plugin API itself. Undo the npm dependency an older
        # release added to package.json; node_modules is left for the user to prune.
        if old_state.get("package_json"):
            restore_package_json(home, old_state.get("package_json"))

        state = {
            "schema": 2,
            "package_version": PACKAGE_VERSION,
            "installed_at": old_state.get("installed_at") or utc_now(),
            "updated_at": utc_now(),
            "backup_dir": str(backup_dir),
            "managed_files": managed,
            "preserved_local": preserved,
            "created_dirs": created_dirs,
            "preflight": probe,
            "opencode_config": config_ownership,
        }
        assert_canonical_state(state)
        write_json(state_path(home), state)
        verify(root, home)
    except Exception:
        rollback_transaction(home, snapshot)
        raise

    if old_state.get("legacy_separator_keys"):
        print(
            f"[!] Normalized {old_state['legacy_separator_keys']} legacy path key(s) "
            "to the POSIX installation-state contract."
        )
    for relative in preserved:
        print(f"[!] PRESERVED local modification: {relative}")
    for note in config_ownership.get("notes") or []:
        print(f"[!] {note}")
    for warning in (probe.get("warnings") or []) if not skip_preflight else []:
        print(f"[!] {warning}")
    print(f"[+] {TITLE} {PACKAGE_VERSION} installed to: {home}")
    print(f"[+] Backup: {backup_dir}")
    print("[*] Project .project-log/ directories are never modified by this installer.")


def verify(root: Path, home: Path) -> None:
    validate_source(root)
    state = read_state(home)
    if not state:
        raise RuntimeError("OpenCode installation state is missing")
    preserved = set(state.get("preserved_local", []))
    if not agents_block_present(root, home):
        raise RuntimeError(f"{AGENTS_RELATIVE} is missing the managed Vibe Coding block")
    for relative, source in managed_sources(root).items():
        target = destination_for(home, relative)
        if not target.is_file():
            raise RuntimeError(f"installed file is missing: {relative}")
        if relative in preserved:
            continue
        if sha256_file(target) != sha256_file(source):
            raise RuntimeError(f"installed file differs from package: {relative}")
    config = read_json(destination_for(home, "opencode.json"), {})
    if not isinstance(config, dict) or config.get("default_agent") != "vibe-main":
        raise RuntimeError("opencode.json default_agent must be vibe-main")
    registered = configured_plugins(config)
    legacy = [item for item in registered if plugin_key(item) in {plugin_key(spec) for spec in LEGACY_LOCAL_PLUGIN_SPECS}]
    if legacy:
        raise RuntimeError(
            f"opencode.json still registers the V1 single-file plugin {legacy[0]!r}, which "
            "OpenCode V2 rejects; rerun the installer update to migrate it"
        )
    if GOAL_PLUGIN_SPEC not in registered:
        raise RuntimeError(
            f"opencode.json does not register the pinned session Goal controller "
            f"({GOAL_PLUGIN_SPEC}); the global rules declare it for OpenCode"
        )
    python_pointer = destination_for(home, "vibe-python")
    if not python_pointer.is_file() or not python_pointer.read_text(encoding="utf-8").strip():
        raise RuntimeError("vibe-python pointer is missing")
    plugin = destination_for(home, PLUGIN_RELATIVE)
    if not plugin.is_file():
        raise RuntimeError("Vibe Workflow plugin asset is missing")
    legacy_file = destination_for(home, "plugins/vibe-workflow.ts")
    if legacy_file.is_file():
        raise RuntimeError(
            "plugins/vibe-workflow.ts (V1 single-file plugin) is still present; OpenCode V2 "
            "tries to load it and fails. Remove it after keeping any local changes."
        )
    if not destination_for(home, f"{RUNTIME_RELATIVE}/scripts/vibe.py").is_file():
        raise RuntimeError("Vibe runtime scripts are missing")
    print("[+] OpenCode installation verification passed.")


def remove_managed_config(home: Path, ownership: Any) -> None:
    config_path = destination_for(home, "opencode.json")
    config = read_json(config_path, None)
    if not isinstance(config, dict):
        return
    own = ownership if isinstance(ownership, dict) else {}

    schema_ownership = own.get("schema")
    if isinstance(schema_ownership, dict) and not schema_ownership.get("present"):
        # Only remove the schema line the installer itself wrote.
        if config.get("$schema") == schema_ownership.get("installed"):
            config.pop("$schema", None)

    agent_ownership = own.get("default_agent")
    if isinstance(agent_ownership, dict) and agent_ownership.get("present"):
        config["default_agent"] = agent_ownership.get("previous")
    else:
        config.pop("default_agent", None)

    # Drop the V1 single-file plugin spec older releases wrote, and the Goal controller the
    # installer added, keeping any entry the user already had before installation.
    plugins_added = own.get("plugins_added")
    removable = {plugin_key(spec) for spec in LEGACY_LOCAL_PLUGIN_SPECS}
    if isinstance(plugins_added, dict):
        removable |= {key for key, present in plugins_added.items() if not present}
    for list_key in ("plugins", "plugin"):
        plugins = config.get(list_key)
        if not isinstance(plugins, list):
            continue
        remaining = [item for item in plugins if plugin_key(item) not in removable]
        if remaining:
            config[list_key] = remaining
        else:
            config.pop(list_key, None)

    permissions = config.get("permission")
    managed_permissions = own.get("permissions_added")
    if isinstance(permissions, dict) and isinstance(managed_permissions, dict):
        for group, patterns in managed_permissions.items():
            current = permissions.get(group)
            if not isinstance(current, dict) or not isinstance(patterns, dict):
                continue
            for pattern, info in patterns.items():
                if not isinstance(info, dict):
                    continue
                if info.get("present"):
                    current[pattern] = info.get("previous")
                elif current.get(pattern) == info.get("installed"):
                    current.pop(pattern, None)
            if not current:
                permissions.pop(group, None)
        if not permissions:
            config.pop("permission", None)
    if own.get("file_created") and not config:
        config_path.unlink()
        return
    write_json(config_path, config)


def uninstall(root: Path, home: Path) -> None:
    state = read_state(home)
    if not state:
        print("[*] No active Vibe OpenCode installation state was found.")
        print("[*] Project .project-log/ directories were not touched.")
        return
    # Validate everything we must edit before deleting anything, so a damaged
    # file can never leave a half-removed installation behind.
    validate_existing_json(home)
    if not agents_block_consistent(home):
        raise RuntimeError(
            f"{AGENTS_RELATIVE} has a damaged managed block; refusing to modify it. Nothing was removed."
        )
    validate_state_shape(state)
    backup_dir = backup(home, "uninstall")
    snapshot = transaction_snapshot(home, tracked_relatives(root))
    try:
        for relative, expected in state.get("managed_files", {}).items():
            target = destination_for(home, relative)
            if not target.is_file():
                continue
            if sha256_file(target) == expected:
                target.unlink()
            else:
                print(f"PRESERVE {relative}: changed after installation")
        remove_agents_block(home)
        remove_managed_config(home, state.get("opencode_config", {}))
        restore_package_json(home, state.get("package_json", {}))
        if state_path(home).exists():
            state_path(home).unlink()
        # Only prune the exact directories this installer created, deepest first.
        # A directory that still holds anything the user put there is left alone.
        for relative in sorted(
            state.get("created_dirs") or [], key=lambda p: p.count("/"), reverse=True
        ):
            target = destination_for(home, relative)
            if target.is_dir():
                try:
                    target.rmdir()
                except OSError:
                    pass
    except Exception:
        rollback_transaction(home, snapshot)
        raise
    print(f"[+] Removed the Vibe OpenCode layer. Backup: {backup_dir}")
    print("[*] Project .project-log/ directories were not touched.")


def main() -> int:
    # A Windows console defaults to a legacy codepage (for example cp1252); printing this
    # CLI's non-ASCII output there raises UnicodeEncodeError. The output contract is UTF-8
    # on every platform, so force the process streams before anything is printed. The
    # getattr check tolerates a harness (or a replaced stream) with no reconfigure().
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("action", choices=("install", "update", "verify", "preflight", "uninstall"))
    parser.add_argument("--opencode-home", help="Override the OpenCode config directory.")
    parser.add_argument("--skip-preflight", action="store_true", help="Only for isolated package tests.")
    parser.add_argument("--skip-plugin-install", action="store_true", help="Accepted for compatibility; OpenCode V2 needs no npm plugin dependency.")
    args = parser.parse_args()
    root = package_root()
    home = config_dir(args.opencode_home)
    try:
        if args.action in {"install", "update"}:
            install_or_update(
                root,
                home,
                skip_preflight=args.skip_preflight,
                skip_plugin_install=args.skip_plugin_install,
            )
        elif args.action == "verify":
            verify(root, home)
        elif args.action == "preflight":
            print(json.dumps(
                preflight(root, home, skip_plugin_install=args.skip_plugin_install),
                ensure_ascii=False, indent=2,
            ))
        else:
            uninstall(root, home)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[X] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
