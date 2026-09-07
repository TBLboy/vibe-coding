#!/usr/bin/env python3
"""Generate a host-specific cc-switch Codex common configuration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


CONFIG_BEGIN = "# VIBE-CODEX-GLOBAL:CONFIG:BEGIN"
CONFIG_END = "# VIBE-CODEX-GLOBAL:CONFIG:END"


def codex_home(value: str | None) -> Path:
    raw = value or os.environ.get("CODEX_HOME")
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".codex").resolve()


def configured_python(home: Path) -> Path:
    configured = os.environ.get("VIBE_PYTHON", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
    else:
        config = home / "vibe-python"
        if not config.is_file():
            raise RuntimeError(f"Missing configured Vibe Python: {config}")
        candidate = Path(config.read_text(encoding="utf-8").strip()).expanduser()
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise RuntimeError(f"Configured Vibe Python does not exist: {candidate}")
    return candidate


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def hook_commands(python: Path, script: Path) -> tuple[str, str]:
    unix_command = f'"{python.as_posix()}" "{script.as_posix()}"'
    # Codex 0.147.0+ on Windows no longer parses quotes in hook commands, so
    # commandWindows must be unquoted. Paths with spaces require manual quoting
    # or short-path substitution; Vibe default paths have no spaces.
    windows_command = f"{python} {script}"
    return unix_command, windows_command


def generate(root: Path, home: Path) -> str:
    python = configured_python(home)
    hooks = home / "vibe-workflow" / "hooks"
    lines = [
        "# Generated for the current host by:",
        "#",
        "#   python3 scripts/generate_cc_switch_config.py \\",
        "#     --output cc-switch-common-config-codex.txt",
        "#",
        "# Do not copy this file between machines without regenerating it. It contains",
        "# host-specific absolute paths for CODEX_HOME, Vibe Python, hooks, and the",
        "# local vibe-coding marketplace.",
        "",
        'model_reasoning_effort = "high"',
        "disable_response_storage = true",
        "",
        CONFIG_BEGIN,
    ]
    for event, filename, context_limit in (
        ("SessionStart", "session_start.py", True),
        ("PostToolUse", "post_tool_use.py", True),
        ("PreCompact", "pre_compact.py", False),
    ):
        command, command_windows = hook_commands(python, hooks / filename)
        lines.extend(
            [
                f"[[hooks.{event}]]",
                f"[[hooks.{event}.hooks]]",
                'type = "command"',
                f"command = {toml_string(command)}",
                f"commandWindows = {toml_string(command_windows)}",
                "timeout = 15",
            ]
        )
        if context_limit:
            lines.append("additionalContextLimit = 2500")
        lines.append("")
    lines.extend(
        [
            "[marketplaces.vibe-global-toolbox]",
            'source_type = "local"',
            f"source = {toml_string(str(root))}",
            "",
            '[plugins."vibe-toolbelt@vibe-global-toolbox"]',
            "enabled = true",
            "",
            CONFIG_END,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    home = codex_home(str(args.codex_home) if args.codex_home else None)
    config = generate(root, home)
    if args.output:
        args.output.expanduser().resolve().write_text(config, encoding="utf-8", newline="\n")
    else:
        print(config, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
