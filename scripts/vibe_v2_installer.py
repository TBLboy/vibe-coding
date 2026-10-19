"""Conservative installer for the clean-room Vibe Coding V2 OpenCode layer.

This installer owns only the V2 runtime files it copies and the exact config
entries it adds. It never installs providers, models, MCPs, external packages,
or user permissions. All writes are preceded by a timestamped backup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone


STATE_FILE = ".vibe-v2-installation-state.json"
PLUGIN_SPEC = "./runtime/opencode/plugins/vibe-v2"
AGENT_FILES = ("vibe-main.md", "vibe-reviewer.md")
COPY_ROOTS = (
    (Path("runtime/core"), Path("runtime/core")),
    (Path("runtime/opencode/plugins/vibe-v2"), Path("runtime/opencode/plugins/vibe-v2")),
    (Path("skills"), Path("skills")),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def home_default() -> Path:
    configured = os.environ.get("OPENCODE_CONFIG_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".config" / "opencode"


def read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise RuntimeError(f"Invalid JSON: {path}: {error}") from error


def write_json_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def assert_within(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"Unsafe destination outside OpenCode home: {candidate}") from error
    return resolved


def source_files(root: Path):
    for source_relative, destination_relative in COPY_ROOTS:
        source_root = root / source_relative
        if not source_root.is_dir():
            raise RuntimeError(f"Missing V2 source directory: {source_root}")
        for source in source_root.rglob("*"):
            if source.is_symlink():
                raise RuntimeError(f"Symlink source is not allowed: {source}")
            if source.is_file():
                yield source, destination_relative / source.relative_to(source_root)
    agent_root = root / "runtime/opencode/agents"
    for name in AGENT_FILES:
        source = agent_root / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"Missing or unsafe V2 agent source: {source}")
        yield source, Path("agents") / name


def state_path(home: Path) -> Path:
    return home / STATE_FILE


def backup(home: Path, paths: list[Path]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    directory = home / "backups" / f"vibe-v2-{stamp}"
    directory.mkdir(parents=True, exist_ok=False)
    for relative in paths:
        source = home / relative
        if source.is_file():
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return directory


def config_path(home: Path) -> Path:
    return home / "opencode.json"


def merge_config(home: Path, previous_state: dict | None) -> dict:
    path = config_path(home)
    existed = path.exists()
    config = read_json(path, {})
    if not isinstance(config, dict):
        raise RuntimeError("opencode.json must contain an object")
    plugins = config.get("plugin")
    if plugins is None:
        plugins = []
    if not isinstance(plugins, list):
        raise RuntimeError("opencode.json plugin must be an array when present")
    added = PLUGIN_SPEC not in plugins
    if added:
        plugins.append(PLUGIN_SPEC)
    config["plugin"] = plugins
    previous_default = config.get("default_agent") if "default_agent" in config else None
    config["default_agent"] = "vibe-main"
    current_ownership = {
        "file_existed": existed,
        "plugin_added": added,
        "default_agent_previous": previous_default,
        "default_agent_was_present": "default_agent" in read_json(path, {}) if existed else False,
    }
    # An update must retain the original ownership facts. Otherwise the second
    # install observes its own plugin/default-agent values, records that it
    # added nothing, and a later uninstall leaves V2 configuration behind.
    prior_ownership = previous_state.get("config") if isinstance(previous_state, dict) else None
    ownership = prior_ownership if isinstance(prior_ownership, dict) else current_ownership
    return {
        "config": config,
        "ownership": ownership,
    }


def install(root: Path, home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    prior = read_json(state_path(home), None)
    if prior is not None and not isinstance(prior, dict):
        raise RuntimeError("V2 installation state is malformed")
    files = list(source_files(root))
    tracked = [Path("opencode.json"), Path(STATE_FILE)] + [relative for _, relative in files]
    backup_dir = backup(home, tracked)
    merged = merge_config(home, prior)
    copied = {}
    created_dirs = set()
    try:
        for source, relative in files:
            target = assert_within(home, home / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            created_dirs.add(str(relative.parent).replace("\\", "/"))
            shutil.copy2(source, target)
            copied[str(relative).replace("\\", "/")] = sha256(target)
        write_json_atomic(config_path(home), merged["config"])
        state = {
            "schema": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "source_root": str(root.resolve()),
            "managed_files": copied,
            "created_dirs": sorted(created_dirs, key=lambda item: (item.count("/"), item)),
            "config": merged["ownership"],
            "backup_dir": str(backup_dir),
        }
        write_json_atomic(state_path(home), state)
    except Exception:
        raise RuntimeError(f"Install failed after backup {backup_dir}; restore from that backup before retrying")
    print(f"[+] Installed Vibe Coding V2 to {home}")
    print(f"[+] Backup: {backup_dir}")


def verify(root: Path, home: Path) -> None:
    state = read_json(state_path(home), None)
    if not isinstance(state, dict):
        raise RuntimeError("No V2 installation state found")
    expected = state.get("managed_files")
    if not isinstance(expected, dict):
        raise RuntimeError("V2 installation state has invalid managed_files")
    failures = []
    for relative, digest in expected.items():
        target = home / relative
        if not target.is_file() or sha256(target) != digest:
            failures.append(relative)
    config = read_json(config_path(home), {})
    if PLUGIN_SPEC not in config.get("plugin", []):
        failures.append("opencode.json: plugin entry")
    if config.get("default_agent") != "vibe-main":
        failures.append("opencode.json: default_agent")
    if failures:
        raise RuntimeError("V2 installation verification failed: " + ", ".join(failures))
    print("[+] Vibe Coding V2 installation verification passed.")


def uninstall(home: Path) -> None:
    state = read_json(state_path(home), None)
    if not isinstance(state, dict):
        print("[*] No V2 installation state found.")
        return
    expected = state.get("managed_files", {})
    if not isinstance(expected, dict):
        raise RuntimeError("V2 installation state has invalid managed_files")
    tracked = [Path("opencode.json"), Path(STATE_FILE)] + [Path(key) for key in expected]
    backup_dir = backup(home, tracked)
    for relative, digest in expected.items():
        target = assert_within(home, home / relative)
        if target.is_file() and sha256(target) == digest:
            target.unlink()
        elif target.exists():
            print(f"PRESERVE {relative}: changed after installation")
    config = read_json(config_path(home), {})
    ownership = state.get("config", {})
    plugins = config.get("plugin")
    if isinstance(plugins, list) and ownership.get("plugin_added"):
        config["plugin"] = [entry for entry in plugins if entry != PLUGIN_SPEC]
    if ownership.get("default_agent_was_present"):
        config["default_agent"] = ownership.get("default_agent_previous")
    elif config.get("default_agent") == "vibe-main":
        config.pop("default_agent", None)
    write_json_atomic(config_path(home), config)
    state_path(home).unlink(missing_ok=True)
    for relative in sorted(state.get("created_dirs", []), key=lambda item: item.count("/"), reverse=True):
        target = home / relative
        try:
            target.rmdir()
        except OSError:
            pass
    print(f"[+] Removed Vibe Coding V2 layer. Backup: {backup_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Vibe Coding V2 conservative OpenCode installer")
    parser.add_argument("action", choices=("install", "verify", "uninstall"))
    parser.add_argument("--opencode-home", type=Path, default=home_default())
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    home = args.opencode_home.expanduser().resolve()
    if args.action == "install":
        install(root, home)
    elif args.action == "verify":
        verify(root, home)
    else:
        uninstall(home)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"[!] {error}", file=sys.stderr)
        raise SystemExit(1)
