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
import tempfile
from datetime import datetime, timezone


STATE_FILE = ".vibe-v2-installation-state.json"
PLUGIN_SPEC = "./runtime/opencode/plugins/vibe-v2"
AGENT_FILES = ("vibe-main.md", "vibe-reviewer.md")
COPY_ROOTS = (
    (Path("runtime/core"), Path("runtime/core")),
    (Path("shared/team-contracts"), Path("shared/team-contracts")),
    (Path("runtime/opencode/plugins/vibe-v2"), Path("runtime/opencode/plugins/vibe-v2")),
    (Path("skills"), Path("skills")),
    (Path("docs"), Path("docs")),
    (Path("schemas"), Path("schemas")),
)
# Running the Python tests creates bytecode caches next to the Skill scripts.
# They are build artifacts, not framework assets, so they must never be copied
# into a user's OpenCode configuration.
EXCLUDED_DIRECTORY_NAMES = frozenset({"__pycache__"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})
# Per-machine user data that a Skill stores inside its own directory (e.g. the archive root).
# It must never be shipped from source nor treated as a managed file.
EXCLUDED_FILE_NAMES = frozenset({"archive_root.conf"})


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
    """Replace `path` atomically while keeping its existing permission bits.

    opencode.json holds provider API keys; a temp-file replace would otherwise reset a
    user's 0600 to the umask default and silently widen read access.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def assert_within(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    resolved = candidate.resolve(strict=False)
    if candidate.absolute() != resolved:
        raise RuntimeError(f"Symlink or noncanonical destination is not allowed: {candidate}")
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"Unsafe destination outside OpenCode home: {candidate}") from error
    return resolved


def prune_empty_parents(home: Path, start: Path) -> None:
    """Remove directories emptied by a deleted managed file.

    An empty `skills/<id>/` still looks like an installed Skill to a directory scan, so a
    removed managed file must not leave one behind. Stop at the first non-empty ancestor.
    """
    parent = start
    while parent != home and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def source_files(root: Path):
    for source_relative, destination_relative in COPY_ROOTS:
        source_root = root / source_relative
        if not source_root.is_dir():
            raise RuntimeError(f"Missing V2 source directory: {source_root}")
        for source in source_root.rglob("*"):
            if source.is_symlink():
                raise RuntimeError(f"Symlink source is not allowed: {source}")
            if source.is_file():
                relative = source.relative_to(source_root)
                if EXCLUDED_DIRECTORY_NAMES.intersection(relative.parts):
                    continue
                if source.suffix.lower() in EXCLUDED_SUFFIXES or source.name in EXCLUDED_FILE_NAMES:
                    continue
                yield source, destination_relative / relative
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
    directory = assert_within(home, home / "backups" / f"vibe-v2-{stamp}")
    directory.mkdir(parents=True, exist_ok=False)
    # The backup contains opencode.json and therefore plaintext credentials: owner-only.
    os.chmod(directory, 0o700)
    for relative in paths:
        source = assert_within(home, home / relative)
        if source.is_file():
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            os.chmod(destination, 0o600)
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


def remove_stale_managed_files(home: Path, prior_state, current: set[str]) -> None:
    """Delete files the previous install managed that the current source no longer ships.

    Only an unmodified copy (hash still equals the recorded hash) is removed; a file the
    user edited is preserved and reported, exactly like uninstall.
    """
    expected = prior_state.get("managed_files") if isinstance(prior_state, dict) else None
    if not isinstance(expected, dict):
        return
    for relative, digest in expected.items():
        if relative in current:
            continue
        target = assert_within(home, home / relative)
        if target.is_file() and sha256(target) == digest:
            target.unlink()
            print(f"[-] Removed stale managed file {relative}")
            prune_empty_parents(home, target.parent)
        elif target.exists():
            print(f"PRESERVE {relative}: no longer managed but changed after installation")


def install(root: Path, home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    assert_within(home, state_path(home))
    assert_within(home, config_path(home))
    prior = read_json(state_path(home), None)
    if prior is not None and not isinstance(prior, dict):
        raise RuntimeError("V2 installation state is malformed")
    files = list(source_files(root))
    expected = prior.get("managed_files", {}) if prior else {}
    if not isinstance(expected, dict):
        raise RuntimeError("Invalid managed_files in installation state")
    # Preflight the entire install before touching any managed file/configuration.
    conflicts = []
    for _, relative in files:
        target = assert_within(home, home / relative)
        key = relative.as_posix()
        if target.exists() and (not target.is_file() or key not in expected or sha256(target) != expected[key]):
            conflicts.append(key)
    if conflicts:
        raise RuntimeError("Install refused; existing unowned or user-modified files must be reconciled explicitly: " + ", ".join(conflicts))
    merged = merge_config(home, prior)
    if prior and read_json(config_path(home), {}).get("default_agent") != "vibe-main":
        raise RuntimeError("Install refused; default_agent was changed by the user. Reconcile explicitly before updating.")
    tracked = list(dict.fromkeys([Path("opencode.json"), Path(STATE_FILE)] + [relative for _, relative in files] + [Path(key) for key in expected]))
    for relative in tracked:
        assert_within(home, home / relative)
    original_modes = {relative: (home / relative).stat().st_mode & 0o777 for relative in tracked if (home / relative).is_file()}
    backup_dir = backup(home, tracked)
    copied = {}
    created_dirs = set()
    try:
        remove_stale_managed_files(home, prior, {str(relative).replace("\\", "/") for _, relative in files})
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
    except Exception as error:
        # Restore pre-install files, including stale managed files; remove newly created files.
        try:
            for relative in tracked:
                target = assert_within(home, home / relative)
                original = backup_dir / relative
                if original.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # Backup permissions are deliberately restrictive; restore original bits separately.
                    shutil.copyfile(original, target)
                    os.chmod(target, original_modes[relative])
                elif target.is_file():
                    target.unlink()
        except Exception as rollback_error:
            raise RuntimeError(f"Install and rollback failed; restore from {backup_dir}: {rollback_error}") from error
        raise RuntimeError(f"Install failed; previous files restored from {backup_dir}: {error}") from error
    print(f"[+] Installed Vibe Coding V2 to {home}")
    print(f"[+] Backup: {backup_dir}")
    print("[!] The backup contains opencode.json with plaintext credentials (owner-only permissions). Delete it once the install is verified.")


def verify(root: Path, home: Path) -> None:
    state = read_json(state_path(home), None)
    if not isinstance(state, dict):
        raise RuntimeError("No V2 installation state found")
    expected = state.get("managed_files")
    if not isinstance(expected, dict):
        raise RuntimeError("V2 installation state has invalid managed_files")
    failures = []
    current = {relative.as_posix(): sha256(source) for source, relative in source_files(root)}
    for relative in sorted(set(expected) | set(current)):
        target = assert_within(home, home / relative)
        if relative not in current or expected.get(relative) != current.get(relative) or not target.is_file() or sha256(target) != current.get(relative):
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
            prune_empty_parents(home, target.parent)
        elif target.exists():
            print(f"PRESERVE {relative}: changed after installation")
    config = read_json(config_path(home), {})
    ownership = state.get("config", {})
    plugins = config.get("plugin")
    if isinstance(plugins, list) and ownership.get("plugin_added"):
        config["plugin"] = [entry for entry in plugins if entry != PLUGIN_SPEC]
    if config.get("default_agent") == "vibe-main":
        if ownership.get("default_agent_was_present"):
            config["default_agent"] = ownership.get("default_agent_previous")
        else:
            config.pop("default_agent", None)
    write_json_atomic(config_path(home), config)
    state_path(home).unlink(missing_ok=True)
    for relative in sorted(state.get("created_dirs", []), key=lambda item: item.count("/"), reverse=True):
        target = assert_within(home, home / relative)
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
