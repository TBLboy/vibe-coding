#!/usr/bin/env python3
"""Install, update, verify, preflight, or remove the Vibe Coding Codex core."""
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
import tomllib
from typing import Any


TITLE = "Vibe Coding - Codex Global Core"
PACKAGE_VERSION = "0.4.1"
BEGIN = "<!-- VIBE-CODEX-GLOBAL:BEGIN -->"
END = "<!-- VIBE-CODEX-GLOBAL:END -->"
CONFIG_BEGIN = "# VIBE-CODEX-GLOBAL:CONFIG:BEGIN"
CONFIG_END = "# VIBE-CODEX-GLOBAL:CONFIG:END"
PLUGIN = "vibe-toolbelt@vibe-global-toolbox"
PLUGIN_MARKETPLACE = "vibe-global-toolbox"
STATE_NAME = ".vibe-codex-installation-state.json"
LEGACY_STATE_NAME = "installation-state.json"
EXCLUDED_NAMES = {"__pycache__", LEGACY_STATE_NAME}
PYTHON_CONFIG_NAME = "vibe-python"
PYTHON_ENV_NAME = "VIBE_PYTHON"
MCP_CATALOG_RELATIVE = Path("runtime/mcp/optional-mcps.json")


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def codex_home(value: str | None) -> Path:
    raw = value or os.environ.get("CODEX_HOME")
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".codex").resolve()


def skill_root(home: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    default_home = (Path.home() / ".codex").resolve()
    agents_skills = (Path.home() / ".agents" / "skills").resolve()
    if home == default_home and agents_skills.is_dir() and not (home / "skills").exists():
        return agents_skills
    return home / "skills"


def norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        yield path, relative


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return ""
    for path, relative in iter_source_files(root):
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def source_skills(root: Path) -> list[Path]:
    skills = sorted(path for path in (root / "skills").iterdir() if path.is_dir())
    if not skills or any(not (skill / "SKILL.md").is_file() for skill in skills):
        raise RuntimeError("Package Skills are incomplete.")
    return skills


def managed_pattern() -> re.Pattern[str]:
    return re.compile(re.escape(BEGIN) + r"[\s\S]*?" + re.escape(END), re.MULTILINE)


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def state_path(home: Path) -> Path:
    return home / STATE_NAME


def read_state(home: Path) -> dict[str, Any]:
    candidates = [state_path(home), home / "vibe-workflow" / LEGACY_STATE_NAME]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def write_state(home: Path, state: dict[str, Any]) -> None:
    state_path(home).write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def backup(home: Path, skills: Path, action: str) -> Path:
    destination = home / "backups" / f"vibe-global-{action}-{stamp()}"
    destination.mkdir(parents=True, exist_ok=True)
    for source, relative in (
        (home / "AGENTS.md", Path("AGENTS.md")),
        (home / "config.toml", Path("config.toml")),
    ):
        if source.is_file():
            shutil.copy2(source, destination / relative)
    runtime = home / "vibe-workflow"
    if runtime.is_dir():
        shutil.copytree(runtime, destination / "vibe-workflow")
    if skills.is_dir():
        for skill in source_skills(package_root()):
            current = skills / skill.name
            if current.is_dir():
                shutil.copytree(current, destination / "skills" / skill.name)
    return destination


def source_prompt(root: Path) -> str:
    prompt = root / "prompts" / "vibe-global-agent.md"
    if not prompt.is_file():
        raise RuntimeError("Global prompt is missing.")
    return prompt.read_text(encoding="utf-8").rstrip()


def install_agents_block(root: Path, home: Path) -> None:
    agents = home / "AGENTS.md"
    old = agents.read_text(encoding="utf-8") if agents.exists() else ""
    block = f"{BEGIN}\n{source_prompt(root)}\n{END}"
    if managed_pattern().search(old):
        merged = managed_pattern().sub(block, old, count=1)
    else:
        merged = old.rstrip() + ("\n\n" if old.rstrip() else "") + block + "\n"
    agents.write_text(merged, encoding="utf-8", newline="\n")


def remove_agents_block(home: Path) -> None:
    agents = home / "AGENTS.md"
    if not agents.exists():
        return
    cleaned = managed_pattern().sub("", agents.read_text(encoding="utf-8"), count=1)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if cleaned:
        agents.write_text(cleaned + "\n", encoding="utf-8", newline="\n")
    else:
        agents.unlink()


def config_block_bounds(text: str) -> tuple[int, int]:
    """Return (start, end) of the managed block; end is -1 when the END marker is missing.

    Third-party config managers (e.g. cc-switch) may rewrite config.toml and
    drop the trailing ``# VIBE-CODEX-GLOBAL:CONFIG:END`` comment while keeping
    the BEGIN marker. Treat everything from BEGIN to EOF as the managed block
    so updates and uninstalls still work instead of failing hard.
    """
    start = text.find(CONFIG_BEGIN)
    if start < 0:
        return -1, -1
    end = text.find(CONFIG_END, start)
    if end < 0:
        return start, -1
    return start, end + len(CONFIG_END)


def strip_config_block(text: str) -> str:
    start, end = config_block_bounds(text)
    if start < 0:
        return text
    if end < 0:
        end = len(text)
    return (text[:start].rstrip() + "\n\n" + text[end:].lstrip()).strip() + "\n"


def _sections_in_block(text: str, prefix: str) -> str:
    """Extract ``[prefix...]`` tables inside the managed block for preservation."""
    start, end = config_block_bounds(text)
    if start < 0:
        return ""
    block = text[start : (end if end >= 0 else len(text))]
    matches = re.findall(
        rf"(?ms)^\[\[?{re.escape(prefix)}(?:\.[^\]]+)?\]\]?\n.*?(?=^\[|\Z)",
        block,
    )
    return "\n\n".join(match.rstrip() for match in matches).strip()


def preserved_provider_sections(text: str) -> str:
    """Keep model_providers tables that third-party tools placed inside the block.

    cc-switch serializes config.toml by interleaving its own ``[model_providers]``
    tables with the managed hooks block. Stripping the block would delete the
    user's model provider configuration, so those tables are extracted first
    and merged back after the block is removed.
    """
    return _sections_in_block(text, "model_providers")


def preserved_mcp_sections(text: str) -> str:
    """Keep MCP entries that older installers placed inside their block.

    Codex's ``mcp add`` may insert a table immediately before the managed
    block marker. Moving those tables outside the regenerated block prevents a
    later ``--without-mcp`` update from silently deleting an existing server.
    """
    return _sections_in_block(text, "mcp_servers")


def toml_string(value: str) -> str:
    return json.dumps(value)


def configured_python(home: Path) -> Path:
    """Resolve the global interpreter used by Vibe runtime commands.

    An explicit VIBE_PYTHON environment variable wins. Otherwise the user-level
    CODEX_HOME/vibe-python file is read. The file contains one executable path
    and is intentionally not managed or deleted by install/update/uninstall.
    Falling back to the interpreter running the installer preserves compatibility
    for isolated tests and older installations.
    """
    raw = os.environ.get(PYTHON_ENV_NAME, "").strip()
    config_path = home / PYTHON_CONFIG_NAME
    if not raw and config_path.is_file():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            candidate_line = line.strip()
            if candidate_line and not candidate_line.startswith("#"):
                raw = candidate_line
                break
    if not raw:
        return Path(sys.executable).resolve()

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        resolved = shutil.which(raw)
        candidate = Path(resolved) if resolved else candidate
    candidate = candidate.resolve()
    if not candidate.is_file():
        source = PYTHON_ENV_NAME if os.environ.get(PYTHON_ENV_NAME, "").strip() else str(config_path)
        raise RuntimeError(f"Configured Vibe Python executable does not exist ({source}): {candidate}")
    return candidate


def managed_config_block(home: Path, access_profile: str, include_hooks: bool) -> str:
    runtime = home / "vibe-workflow" / "hooks"
    session = runtime / "session_start.py"
    post_tool = runtime / "post_tool_use.py"
    compact = runtime / "pre_compact.py"
    lines = [CONFIG_BEGIN]
    if access_profile == "workspace":
        lines.extend(['approval_policy = "on-request"', 'sandbox_mode = "workspace-write"', ""])
    elif access_profile == "full":
        lines.extend(['approval_policy = "never"', 'sandbox_mode = "danger-full-access"', ""])

    python = configured_python(home)

    def add_hook(event: str, script: Path) -> None:
        unix_command = f'"{python.as_posix()}" "{script.as_posix()}"'
        windows_command = f'"{python}" "{script}"'
        lines.extend(
            [
                f"[[hooks.{event}]]",
                f"[[hooks.{event}.hooks]]",
                'type = "command"',
                f"command = {toml_string(unix_command)}",
                f"commandWindows = {toml_string(windows_command)}",
                "timeout = 15",
            ]
        )
        if event != "PreCompact":
            lines.append("additionalContextLimit = 2500")
        lines.append("")

    if include_hooks:
        add_hook("SessionStart", session)
        add_hook("PostToolUse", post_tool)
        add_hook("PreCompact", compact)
    lines.append(CONFIG_END)
    return "\n".join(lines)


def install_config(home: Path, *, without_hooks: bool, access_profile: str) -> None:
    path = home / "config.toml"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    preserved_mcp = preserved_mcp_sections(old)
    preserved_providers = preserved_provider_sections(old)
    base = strip_config_block(old) if CONFIG_BEGIN in old else old
    try:
        parsed = tomllib.loads(base) if base.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"existing config.toml is invalid: {exc}") from exc
    if access_profile != "keep-existing":
        conflicts = [key for key in ("approval_policy", "sandbox_mode", "default_permissions") if key in parsed]
        if conflicts:
            raise RuntimeError(
                "access profile would replace existing permission settings: "
                + ", ".join(conflicts)
                + ". Use --access-profile keep-existing or remove the conflicting settings explicitly."
            )
    if without_hooks and access_profile == "keep-existing":
        if CONFIG_BEGIN in old:
            merged = base.rstrip()
            if preserved_providers:
                merged += ("\n\n" if merged else "") + preserved_providers
            if preserved_mcp:
                merged += ("\n\n" if merged else "") + preserved_mcp
            path.write_text((merged + "\n") if merged else "", encoding="utf-8", newline="\n")
        return
    block = managed_config_block(home, access_profile, include_hooks=not without_hooks)
    merged = base.rstrip() + ("\n\n" if base.rstrip() else "")
    if preserved_providers:
        merged += preserved_providers + "\n\n"
    merged += block + "\n"
    if preserved_mcp:
        merged += "\n" + preserved_mcp + "\n"
    try:
        tomllib.loads(merged)
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"managed config merge is invalid: {exc}") from exc
    path.write_text(merged, encoding="utf-8", newline="\n")


def remove_config(home: Path) -> None:
    path = home / "config.toml"
    if not path.exists():
        return
    old = path.read_text(encoding="utf-8")
    if CONFIG_BEGIN not in old:
        return
    preserved = _sections_in_block(old, "model_providers")
    mcp = preserved_mcp_sections(old)
    if preserved:
        preserved += "\n\n" + mcp if mcp else ""
    elif mcp:
        preserved = mcp
    cleaned = strip_config_block(old)
    if preserved:
        cleaned = (cleaned.rstrip() + "\n\n" + preserved).strip() + "\n"
    if cleaned.strip():
        path.write_text(cleaned, encoding="utf-8", newline="\n")
    else:
        path.unlink()


def source_file_map(root: Path) -> dict[str, tuple[Path, str]]:
    files: dict[str, tuple[Path, str]] = {}
    runtime = root / "runtime"
    for path, relative in iter_source_files(runtime):
        key = f"runtime/{relative.as_posix()}"
        files[key] = (path, sha256_file(path))
    for skill in source_skills(root):
        for path, relative in iter_source_files(skill):
            key = f"skills/{skill.name}/{relative.as_posix()}"
            files[key] = (path, sha256_file(path))
    return files


def legacy_managed_files(home: Path, skills: Path, state: dict[str, Any]) -> dict[str, str]:
    if state.get("schema") == 2:
        return dict(state.get("managed_files", {}))
    managed: dict[str, str] = {}
    runtime = home / "vibe-workflow"
    expected_runtime = state.get("runtime_hash")
    if expected_runtime and tree_hash(runtime) == expected_runtime:
        for path, relative in iter_source_files(runtime):
            managed[f"runtime/{relative.as_posix()}"] = sha256_file(path)
    for name, expected_hash in state.get("skills", {}).items():
        current = skills / name
        if expected_hash and tree_hash(current) == expected_hash:
            for path, relative in iter_source_files(current):
                managed[f"skills/{name}/{relative.as_posix()}"] = sha256_file(path)
    return managed


def destination_for(home: Path, skills: Path, key: str) -> Path:
    if key.startswith("runtime/"):
        return home / "vibe-workflow" / key.removeprefix("runtime/")
    if key.startswith("skills/"):
        return skills / key.removeprefix("skills/")
    raise ValueError(key)


def plan_sync(
    home: Path,
    skills: Path,
    sources: dict[str, tuple[Path, str]],
    previous: dict[str, str],
) -> tuple[list[tuple[str, str]], list[str], list[str], dict[str, str]]:
    operations: list[tuple[str, str]] = []
    conflicts: list[str] = []
    preserved: list[str] = []
    managed: dict[str, str] = {}
    for key, (_, source_hash) in sources.items():
        destination = destination_for(home, skills, key)
        current_hash = sha256_file(destination) if destination.is_file() else None
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
        if key in sources:
            continue
        destination = destination_for(home, skills, key)
        if not destination.exists():
            continue
        if destination.is_file() and sha256_file(destination) == previous_hash:
            operations.append(("remove", key))
        else:
            conflicts.append(f"{key}: removed by package but locally modified")
            preserved.append(key)
            managed[key] = previous_hash
    return operations, conflicts, preserved, managed


def apply_sync(
    home: Path,
    skills: Path,
    sources: dict[str, tuple[Path, str]],
    operations: list[tuple[str, str]],
) -> None:
    for action, key in operations:
        destination = destination_for(home, skills, key)
        if action == "copy":
            source = sources[key][0]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        elif action == "remove" and destination.is_file():
            destination.unlink()
    for root in (home / "vibe-workflow", skills):
        if not root.is_dir():
            continue
        for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass


def plugin_env(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(home)
    return environment


def load_optional_mcp_catalog(root: Path) -> dict[str, dict[str, Any]]:
    path = root / MCP_CATALOG_RELATIVE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"optional MCP catalog is invalid: {path}: {exc}") from exc
    entries = payload.get("mcps") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise RuntimeError("optional MCP catalog must contain a 'mcps' list")
    catalog: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise RuntimeError("optional MCP catalog contains an invalid entry")
        name = entry["name"]
        if name in catalog:
            raise RuntimeError(f"optional MCP catalog contains duplicate entry: {name}")
        catalog[name] = entry
    return catalog


def optional_mcp_names(state: dict[str, Any]) -> list[str]:
    configured = state.get("optional_mcps")
    if isinstance(configured, list):
        return [name for name in configured if isinstance(name, str)]
    # Preserve installations created before the catalog existed.
    if state.get("mcp_plugin_installed"):
        return ["vibe-toolbelt"]
    return []


def command_for_mcp(entry: dict[str, Any]) -> list[str]:
    command = entry.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        raise RuntimeError(f"optional MCP {entry.get('name')!r} has an invalid command")
    executable = shutil.which(command[0])
    if executable:
        return [executable, *command[1:]]
    fallback = entry.get("fallback_command")
    if isinstance(fallback, list) and fallback and all(isinstance(part, str) for part in fallback):
        if shutil.which(fallback[0]):
            return fallback
    raise RuntimeError(
        f"optional MCP {entry.get('name')!r} requires {command[0]!r}; "
        "install its prerequisite or provide the command on PATH"
    )


def mcp_get(home: Path, name: str) -> subprocess.CompletedProcess[str] | None:
    codex = shutil.which("codex")
    if not codex:
        return None
    return run_command([codex, "mcp", "get", name], env=plugin_env(home))


def mcp_output_matches(output: str, command: list[str]) -> bool:
    actual_command = next((line.split(":", 1)[1].strip() for line in output.splitlines() if line.strip().startswith("command:")), "")
    actual_args = next((line.split(":", 1)[1].strip() for line in output.splitlines() if line.strip().startswith("args:")), "")
    if not actual_command:
        return False
    return Path(actual_command).name == Path(command[0]).name and actual_args == " ".join(command[1:])


def run_plugin(home: Path, root: Path, *, entry: dict[str, Any] | None = None, remove: bool = False) -> bool:
    plugin = entry.get("plugin", PLUGIN) if entry else PLUGIN
    marketplace = entry.get("marketplace", PLUGIN_MARKETPLACE) if entry else PLUGIN_MARKETPLACE
    codex = shutil.which("codex")
    if codex is None:
        if remove:
            print("[!] codex CLI was not found; skipped optional MCP removal.")
            return False
        raise RuntimeError("codex CLI was not found; cannot install the selected vibe-toolbelt MCP")
    environment = plugin_env(home)
    if remove:
        subprocess.run([codex, "plugin", "remove", plugin], env=environment, check=False)
        subprocess.run([codex, "plugin", "marketplace", "remove", marketplace], env=environment, check=False)
        return True
    subprocess.run([codex, "plugin", "marketplace", "add", str(root)], env=environment, check=True)
    subprocess.run([codex, "plugin", "add", plugin], env=environment, check=True)
    return True


def install_optional_mcp(home: Path, root: Path, entry: dict[str, Any]) -> tuple[bool, bool]:
    name = entry["name"]
    kind = entry.get("kind")
    if kind == "codex-plugin":
        return run_plugin(home, root, entry=entry), True
    if kind != "codex-stdio":
        raise RuntimeError(f"optional MCP {name!r} has unsupported kind: {kind!r}")
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("codex CLI was not found; cannot install the selected MCP")
    command = command_for_mcp(entry)
    existing = mcp_get(home, name)
    if existing and existing.returncode == 0:
        if mcp_output_matches(existing.stdout, command):
            print(f"[*] Optional MCP already configured: {name}")
            return True, False
        raise RuntimeError(f"MCP configuration conflict for {name!r}; existing Codex entry differs")
    subprocess.run([codex, "mcp", "add", name, "--", *command], env=plugin_env(home), check=True)
    return True, True


def verify_optional_mcp(home: Path, root: Path, entry: dict[str, Any]) -> None:
    name = entry["name"]
    if entry.get("kind") == "codex-plugin":
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("codex CLI was not found; cannot verify the selected vibe-toolbelt MCP")
        result = run_command([codex, "plugin", "list"], env=plugin_env(home))
        plugin = entry.get("plugin", PLUGIN)
        if result.returncode or plugin not in result.stdout or "installed, enabled" not in result.stdout:
            raise RuntimeError(f"Optional {name} MCP plugin is not installed and enabled.")
        return
    result = mcp_get(home, name)
    if result is None or result.returncode:
        raise RuntimeError(f"Optional MCP {name!r} is not configured in Codex.")
    command = command_for_mcp(entry)
    if not mcp_output_matches(result.stdout, command):
        raise RuntimeError(f"Optional MCP {name!r} configuration differs from the catalog.")


def remove_optional_mcp(home: Path, root: Path, entry: dict[str, Any]) -> bool:
    if entry.get("kind") == "codex-plugin":
        return run_plugin(home, root, entry=entry, remove=True)
    codex = shutil.which("codex")
    if not codex:
        print(f"[!] codex CLI was not found; skipped optional MCP removal: {entry['name']}")
        return False
    subprocess.run([codex, "mcp", "remove", entry["name"]], env=plugin_env(home), check=False)
    return True


def run_command(command: list[str], *, timeout: int = 30, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=env,
        check=False,
    )


def preflight(home: Path, *, skip_doctor: bool = False) -> dict[str, Any]:
    python = configured_python(home)
    if sys.version_info < (3, 11):
        raise RuntimeError(
            "Python 3.11 or newer is required. Run the installer with the configured Vibe Python: "
            f"{python}"
        )
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Codex CLI is not installed or not on PATH.")
    version = run_command([codex, "--version"])
    if version.returncode:
        raise RuntimeError("codex --version failed:\n" + version.stdout)
    features = run_command([codex, "features", "list"], env=plugin_env(home))
    if features.returncode:
        raise RuntimeError("codex features list failed:\n" + features.stdout)
    feature_state: dict[str, dict[str, Any]] = {}
    for line in features.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            feature_state[parts[0]] = {"stage": " ".join(parts[1:-1]), "enabled": parts[-1].lower() == "true"}
    missing = [name for name in ("goals", "hooks", "multi_agent") if not feature_state.get(name, {}).get("enabled")]
    if missing:
        raise RuntimeError("required Codex capabilities are unavailable or disabled: " + ", ".join(missing))
    doctor_result: dict[str, Any] | None = None
    if not skip_doctor:
        doctor = run_command([codex, "doctor", "--json"], timeout=60, env=plugin_env(home))
        try:
            report = json.loads(doctor.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("codex doctor returned invalid JSON:\n" + doctor.stdout[-4000:]) from exc
        failures = [
            check
            for check in report.get("checks", {}).values()
            if isinstance(check, dict) and check.get("status") == "fail"
        ]
        blocking_categories = {"auth", "config", "runtime", "state"}
        blocking = [check for check in failures if check.get("category") in blocking_categories]
        doctor_result = {
            "overall_status": report.get("overallStatus"),
            "blocking_failures": blocking,
            "nonblocking_failures": failures,
        }
        if blocking:
            summaries = "; ".join(f"{check.get('id')}: {check.get('summary')}" for check in blocking)
            raise RuntimeError("codex doctor reported blocking failures: " + summaries)
    return {
        "codex_version": version.stdout.strip(),
        "features": feature_state,
        "doctor": doctor_result,
        "python_version": sys.version.split()[0],
        "python_executable": str(python),
    }


def validate_source_package(root: Path, home: Path) -> None:
    validator = root / "runtime/scripts/validate_package.py"
    result = run_command([str(configured_python(home)), str(validator), "--root", str(root)])
    if result.returncode:
        raise RuntimeError(result.stdout)


def install_or_update(
    root: Path,
    home: Path,
    skills: Path,
    *,
    mcp_names: list[str] | None,
    without_mcp: bool,
    without_hooks: bool,
    access_profile: str,
    skip_preflight: bool,
    skip_doctor: bool,
) -> None:
    home.mkdir(parents=True, exist_ok=True)
    validate_source_package(root, home)
    skills.mkdir(parents=True, exist_ok=True)
    old_state = read_state(home)
    probe = old_state.get("preflight") if skip_preflight else preflight(home, skip_doctor=skip_doctor)
    catalog = load_optional_mcp_catalog(root)
    if without_mcp and mcp_names:
        raise RuntimeError("--mcp and --without-mcp cannot be used together")
    if without_mcp:
        selected_mcps: list[str] = []
        print("[*] Optional MCPs skipped by --without-mcp.")
    elif mcp_names is None:
        # New installations are core-only by default; updates preserve the
        # optional MCPs explicitly enabled by an earlier installation.
        selected_mcps = optional_mcp_names(old_state) if old_state else []
        if selected_mcps:
            print("[*] Preserving selected optional MCPs: " + ", ".join(selected_mcps))
    else:
        selected_mcps = list(dict.fromkeys(mcp_names))
    unknown = sorted(set(selected_mcps) - set(catalog))
    if unknown:
        available = ", ".join(sorted(catalog)) or "(none)"
        raise RuntimeError(f"unknown optional MCP(s): {', '.join(unknown)}; available: {available}")

    sources = source_file_map(root)
    previous = legacy_managed_files(home, skills, old_state)
    operations, conflicts, preserved, managed = plan_sync(home, skills, sources, previous)
    if conflicts:
        raise RuntimeError("Upgrade conflicts detected before writing:\n- " + "\n- ".join(conflicts))

    backup_dir = backup(home, skills, "update" if old_state else "install")
    original_backup = old_state.get("original_backup_dir") or str(backup_dir)
    install_agents_block(root, home)
    install_config(home, without_hooks=without_hooks, access_profile=access_profile)
    apply_sync(home, skills, sources, operations)

    owned_mcps: list[str] = []
    for name in selected_mcps:
        _, owned = install_optional_mcp(home, root, catalog[name])
        if owned:
            owned_mcps.append(name)

    plugin_installed = "vibe-toolbelt" in selected_mcps

    state = {
        "schema": 2,
        "package_version": PACKAGE_VERSION,
        "installed_at": old_state.get("installed_at") or utc_now(),
        "updated_at": utc_now(),
        "backup_dir": str(backup_dir),
        "original_backup_dir": original_backup,
        "skill_root": str(skills),
        "managed_files": managed,
        "preserved_local": preserved,
        "hooks_installed": not without_hooks,
        "access_profile": access_profile,
        # Keep the legacy bit for older uninstallers while making the state
        # extensible to multiple optional MCPs.
        "mcp_plugin_installed": plugin_installed,
        "optional_mcps": selected_mcps,
        "optional_mcps_owned": owned_mcps,
        "preflight": probe,
    }
    write_state(home, state)
    verify(root, home, skills, check_plugin=plugin_installed)
    print(f"[+] {TITLE} {PACKAGE_VERSION} installed to: {home}")
    print(f"[+] Skills: {skills}")
    print(f"[+] Backup: {backup_dir}")


def verify(root: Path, home: Path, skills: Path, *, check_plugin: bool = False) -> None:
    validate_source_package(root, home)
    agents = home / "AGENTS.md"
    if not agents.is_file():
        raise RuntimeError(f"Global AGENTS.md is missing: {agents}")
    match = managed_pattern().search(agents.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError("Vibe global managed block is missing.")
    inner = match.group(0)[len(BEGIN) : -len(END)].strip()
    if norm(inner) != norm(source_prompt(root)):
        raise RuntimeError("Installed global prompt differs from this package.")
    state = read_state(home)
    preserved = set(state.get("preserved_local", []))
    for key, (_, expected_hash) in source_file_map(root).items():
        target = destination_for(home, skills, key)
        if not target.is_file():
            raise RuntimeError(f"installed file is missing: {key}")
        if key in preserved:
            print(f"[!] PRESERVED local modification: {key}")
            continue
        if sha256_file(target) != expected_hash:
            raise RuntimeError(f"installed file differs from package: {key}")
    if state.get("hooks_installed"):
        config = home / "config.toml"
        if not config.is_file() or CONFIG_BEGIN not in config.read_text(encoding="utf-8"):
            raise RuntimeError("Vibe Hook config block is missing.")
        tomllib.loads(config.read_text(encoding="utf-8"))
    catalog = load_optional_mcp_catalog(root)
    selected_mcps = optional_mcp_names(state)
    if selected_mcps:
        if shutil.which("codex") is None:
            raise RuntimeError("Codex CLI is required to verify selected optional MCPs.")
        for name in selected_mcps:
            if name not in catalog:
                raise RuntimeError(f"installation state references unknown optional MCP: {name}")
            verify_optional_mcp(home, root, catalog[name])
    elif check_plugin and shutil.which("codex") is not None:
        # Compatibility with manually authored legacy state files.
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("codex CLI was not found; cannot verify the selected vibe-toolbelt MCP")
        result = run_command([codex, "plugin", "list"], env=plugin_env(home))
        if result.returncode or PLUGIN not in result.stdout or "installed, enabled" not in result.stdout:
            raise RuntimeError("Optional vibe-toolbelt plugin is not installed and enabled.")
    print("[+] Global installation verification passed.")


def restore_backup_files(backup_dir: Path, home: Path, skills: Path) -> None:
    mappings = [
        (backup_dir / "vibe-workflow", home / "vibe-workflow"),
        (backup_dir / "skills", skills),
    ]
    for source_root, target_root in mappings:
        if not source_root.is_dir():
            continue
        for source, relative in iter_source_files(source_root):
            destination = target_root / relative
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)


def remove_empty_directories(root: Path) -> None:
    if not root.is_dir():
        return
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    try:
        root.rmdir()
    except OSError:
        pass


def uninstall(root: Path, home: Path, skills: Path) -> None:
    state = read_state(home)
    has_managed_agents = (home / "AGENTS.md").is_file() and BEGIN in (home / "AGENTS.md").read_text(encoding="utf-8")
    has_managed_config = (home / "config.toml").is_file() and CONFIG_BEGIN in (home / "config.toml").read_text(encoding="utf-8")
    if not state and not has_managed_agents and not has_managed_config:
        remove_empty_directories(home / "vibe-workflow")
        remove_empty_directories(skills)
        print("[*] No active Vibe installation state was found.")
        return
    backup_dir = backup(home, skills, "uninstall")
    remove_agents_block(home)
    remove_config(home)
    for key, expected_hash in state.get("managed_files", {}).items():
        destination = destination_for(home, skills, key)
        if not destination.is_file():
            continue
        if sha256_file(destination) == expected_hash:
            destination.unlink()
        else:
            print(f"PRESERVE {key}: changed after installation")
    original = Path(state.get("original_backup_dir", "")) if state.get("original_backup_dir") else None
    if original and original.is_dir():
        restore_backup_files(original, home, skills)
    catalog = load_optional_mcp_catalog(root)
    owned = state.get("optional_mcps_owned")
    if isinstance(owned, list):
        for name in owned:
            if isinstance(name, str) and name in catalog:
                remove_optional_mcp(home, root, catalog[name])
    elif state.get("mcp_plugin_installed"):
        run_plugin(home, root, remove=True)
    if state_path(home).exists():
        state_path(home).unlink()
    remove_empty_directories(home / "vibe-workflow")
    remove_empty_directories(skills)
    print(f"[+] Removed the Vibe-managed global layer. Backup: {backup_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("action", choices=("install", "update", "verify", "preflight", "uninstall"))
    parser.add_argument("--codex-home", help="Override CODEX_HOME for isolated tests or another profile.")
    parser.add_argument("--skills-root", help="Override the detected user Skill root.")
    parser.add_argument(
        "--mcp",
        dest="mcp_names",
        action="append",
        metavar="NAME",
        help="Enable an optional MCP from runtime/mcp/optional-mcps.json (repeatable).",
    )
    parser.add_argument("--without-mcp", action="store_true", help="Do not install optional MCPs (legacy compatibility).")
    parser.add_argument("--without-hooks", action="store_true")
    parser.add_argument("--access-profile", choices=("keep-existing", "workspace", "full"), default="keep-existing")
    parser.add_argument("--skip-preflight", action="store_true", help="Only for isolated package tests.")
    parser.add_argument("--skip-doctor", action="store_true")
    args = parser.parse_args()
    root = package_root()
    home = codex_home(args.codex_home)
    skills = skill_root(home, args.skills_root)
    try:
        if args.action in {"install", "update"}:
            install_or_update(
                root,
                home,
                skills,
                mcp_names=args.mcp_names,
                without_mcp=args.without_mcp,
                without_hooks=args.without_hooks,
                access_profile=args.access_profile,
                skip_preflight=args.skip_preflight,
                skip_doctor=args.skip_doctor,
            )
        elif args.action == "verify":
            state = read_state(home)
            verify(root, home, Path(state.get("skill_root", skills)), check_plugin=bool(state.get("mcp_plugin_installed")))
        elif args.action == "preflight":
            print(json.dumps(preflight(home, skip_doctor=args.skip_doctor), ensure_ascii=False, indent=2))
        else:
            state = read_state(home)
            uninstall(root, home, Path(state.get("skill_root", skills)))
        return 0
    except Exception as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
