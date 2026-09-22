#!/usr/bin/env python3
"""Install, update, verify, or remove the Vibe Coding OpenCode client surface."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
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
PLUGIN_RELATIVE = "plugins/vibe-workflow.ts"
DEFAULT_PLUGIN_SPEC = "./plugins/vibe-workflow.ts"
AGENTS_RELATIVE = "AGENTS.md"
AGENTS_BEGIN = "<!-- VIBE-OPENCODE-GLOBAL:BEGIN -->"
AGENTS_END = "<!-- VIBE-OPENCODE-GLOBAL:END -->"
OPENCODE_PACKAGE = "@opencode-ai/plugin"
OPENCODE_PACKAGE_VERSION = "1.18.4"
EXCLUDED_NAMES = {"__pycache__", "node_modules"}
ASSET_DIRECTORIES = ("agents", "commands", "plugins")
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
    return value if isinstance(value, dict) else {}


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
                assets[str(path.relative_to(surface))] = path
    skills = root / SKILLS_RELATIVE
    for path in sorted(skills.glob("*/SKILL.md")):
        assets[str(path.relative_to(root))] = path
        for extra in sorted(path.parent.rglob("*")):
            if extra.is_file() and not any(part in EXCLUDED_NAMES for part in extra.parts):
                assets[str(extra.relative_to(root))] = extra
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
        assets[str(relative)] = path
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


def destination_for(home: Path, relative: str) -> Path:
    safe = safe_relative(relative)
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
            if safe_relative(relative) is None:
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
        if safe_relative(relative) is None:
            raise RuntimeError(f"installation state has an unsafe directory path: {relative!r}")


def plan_sync(
    home: Path,
    sources: dict[str, Path],
    previous: dict[str, str],
) -> tuple[list[tuple[str, str]], list[str], list[str], dict[str, str]]:
    """Decide copy/remove operations and surface conflicts before any write.

    Mirrors the Codex installer semantics: a file that already exists and does
    not match the package is a hard conflict, never a silent overwrite.
    """
    operations: list[tuple[str, str]] = []
    conflicts: list[str] = []
    preserved: list[str] = []
    managed: dict[str, str] = {}
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


def detect_package_manager() -> str | None:
    for candidate in ("npm", "bun"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def preflight(root: Path, home: Path, *, skip_plugin_install: bool) -> dict[str, Any]:
    validate_source(root)
    report: dict[str, Any] = {
        "python": detect_python(root, home),
        "opencode": detect_opencode(),
        "package_manager": detect_package_manager(),
        "config_dir": str(home),
        "plugin_install": "skipped" if skip_plugin_install else "required",
    }
    if not skip_plugin_install and not report["package_manager"]:
        raise RuntimeError("npm or bun is required to install the OpenCode plugin dependency")
    return report


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
    plugins = existing.get("plugin")
    if plugins is None:
        plugins = []
    if not isinstance(plugins, list):
        raise RuntimeError("opencode.json plugin must be a list")
    spec_key = plugin_key(DEFAULT_PLUGIN_SPEC)
    plugin_ownership = previous.get("plugin")
    if not isinstance(plugin_ownership, dict) or "present" not in plugin_ownership:
        plugin_ownership = {"present": any(plugin_key(item) == spec_key for item in plugins)}
    ownership["plugin"] = plugin_ownership
    kept = [item for item in plugins if plugin_key(item) != spec_key]
    merged["plugin"] = dedupe_plugins([*kept, DEFAULT_PLUGIN_SPEC])

    # --- managed permission rules -----------------------------------------
    permissions = dict(existing.get("permission")) if isinstance(existing.get("permission"), dict) else {}
    source_permission = source.get("permission") if isinstance(source.get("permission"), dict) else {}
    previous_permissions = previous.get("permissions_added")
    if not isinstance(previous_permissions, dict):
        previous_permissions = {}
    permissions_ownership: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
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


def install_plugin_dependency(home: Path, package_manager: str) -> dict[str, Any]:
    package_json = destination_for(home, "package.json")
    # Defense in depth: never let the package manager write through an escaping link.
    destination_for(home, "node_modules")
    existed = package_json.is_file()
    package = read_json(package_json, {})
    if package is None:
        package = {}
    if not isinstance(package, dict):
        raise RuntimeError(f"{package_json} must contain a JSON object")
    dependencies = package.get("dependencies")
    if not isinstance(dependencies, dict):
        dependencies = {}
    previous_dependency = dependencies.get(OPENCODE_PACKAGE)
    dependencies[OPENCODE_PACKAGE] = OPENCODE_PACKAGE_VERSION
    package["dependencies"] = dependencies
    write_json(package_json, package)

    command = [package_manager, "install"]
    if Path(package_manager).name == "npm":
        command += ["--no-audit", "--no-fund"]
    result = subprocess.run(
        command, cwd=home, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to install {OPENCODE_PACKAGE}:\n{result.stdout}")
    return {"existed": existed, "previous_dependency": previous_dependency}


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
        dependencies.pop(OPENCODE_PACKAGE, None)
    else:
        dependencies[OPENCODE_PACKAGE] = previous_dependency
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
    probe = old_state.get("preflight") if skip_preflight else preflight(root, home, skip_plugin_install=skip_plugin_install)
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

        package_ownership = old_state.get("package_json") if skip_plugin_install else None
        if not skip_plugin_install:
            manager = probe.get("package_manager") or detect_package_manager()
            if not manager:
                raise RuntimeError("npm or bun is required to install the OpenCode plugin dependency")
            package_ownership = install_plugin_dependency(home, manager)

        state = {
            "schema": 2,
            "package_version": PACKAGE_VERSION,
            "installed_at": old_state.get("installed_at") or utc_now(),
            "updated_at": utc_now(),
            "backup_dir": str(backup_dir),
            "managed_files": managed,
            "preserved_local": preserved,
            "created_dirs": created_dirs,
            "plugin_install": "skipped" if skip_plugin_install else "installed",
            "preflight": probe,
            "opencode_config": config_ownership,
            "package_json": package_ownership,
        }
        write_json(state_path(home), state)
        verify(root, home)
    except Exception:
        rollback_transaction(home, snapshot)
        raise

    for relative in preserved:
        print(f"[!] PRESERVED local modification: {relative}")
    for note in config_ownership.get("notes") or []:
        print(f"[!] {note}")
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
    if DEFAULT_PLUGIN_SPEC not in (config.get("plugin") or []):
        raise RuntimeError("opencode.json does not register the Vibe Workflow plugin")
    python_pointer = destination_for(home, "vibe-python")
    if not python_pointer.is_file() or not python_pointer.read_text(encoding="utf-8").strip():
        raise RuntimeError("vibe-python pointer is missing")
    plugin = destination_for(home, PLUGIN_RELATIVE)
    if not plugin.is_file():
        raise RuntimeError("Vibe Workflow plugin asset is missing")
    if not destination_for(home, f"{RUNTIME_RELATIVE}/scripts/vibe.py").is_file():
        raise RuntimeError("Vibe runtime scripts are missing")
    if state.get("plugin_install") == "installed":
        manifest = destination_for(home, "node_modules/@opencode-ai/plugin/package.json")
        if not manifest.is_file():
            raise RuntimeError(f"{OPENCODE_PACKAGE} dependency is not installed")
        installed = read_json(manifest, {}).get("version")
        if installed != OPENCODE_PACKAGE_VERSION:
            raise RuntimeError(
                f"{OPENCODE_PACKAGE} version mismatch: {installed!r} != {OPENCODE_PACKAGE_VERSION!r}"
            )
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

    plugins = config.get("plugin")
    plugin_ownership = own.get("plugin")
    if isinstance(plugins, list) and not (
        isinstance(plugin_ownership, dict) and plugin_ownership.get("present")
    ):
        spec_key = plugin_key(DEFAULT_PLUGIN_SPEC)
        remaining = [item for item in plugins if plugin_key(item) != spec_key]
        if remaining:
            config["plugin"] = remaining
        else:
            config.pop("plugin", None)

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
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("action", choices=("install", "update", "verify", "preflight", "uninstall"))
    parser.add_argument("--opencode-home", help="Override the OpenCode config directory.")
    parser.add_argument("--skip-preflight", action="store_true", help="Only for isolated package tests.")
    parser.add_argument("--skip-plugin-install", action="store_true", help="Do not install the npm dependency.")
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
