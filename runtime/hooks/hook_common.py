#!/usr/bin/env python3
"""Shared helpers for Vibe command Hooks."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from init_project import initialize_project
from loop_state import append_event, generate_handoff, initialize_loop, load_active_run, project_log


PATH_KEYS = {"path", "file", "file_path", "filepath", "target", "destination"}
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def read_input() -> dict[str, Any]:
    text = sys.stdin.read()
    if not text.strip():
        return {}
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def candidate_cwd(payload: dict[str, Any]) -> Path:
    for key in ("project_root", "cwd", "working_directory", "workspace_root"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return Path(value).expanduser().resolve()
    return Path.cwd().resolve()


def find_project_root(start: Path) -> Path:
    current = start if start.is_dir() else start.parent
    for candidate in (current, *current.parents):
        if (candidate / ".project-log").is_dir() or (candidate / ".git").exists():
            return candidate
    return current


def ensure_project(payload: dict[str, Any]) -> Path:
    root = find_project_root(candidate_cwd(payload))
    if not project_log(root).is_dir():
        initialize_project(root)
    initialize_loop(root)
    return root


def extract_paths(payload: Any) -> list[str]:
    results: list[str] = []

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, child_key.lower())
        elif isinstance(value, list):
            for child in value:
                visit(child, key)
        elif isinstance(value, str):
            if key in PATH_KEYS:
                results.append(value)
            if "*** " in value and " File:" in value:
                results.extend(match.strip() for match in PATCH_PATH_RE.findall(value))

    visit(payload)
    return list(dict.fromkeys(results))


def tool_name(payload: dict[str, Any]) -> str:
    for key in ("tool_name", "toolName", "name"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    tool = payload.get("tool")
    if isinstance(tool, dict):
        for key in ("name", "tool_name"):
            value = tool.get(key)
            if isinstance(value, str):
                return value
    return "unknown"


def maybe_probe(root: Path, hook_name: str, payload: dict[str, Any]) -> None:
    if os.environ.get("VIBE_HOOK_PROBE") != "1":
        return
    path = project_log(root) / "loop/hook-samples.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"hook": hook_name, "payload": payload}, ensure_ascii=False) + "\n")


def compact_context(root: Path) -> str:
    state = load_active_run(root)
    handoff = generate_handoff(root)
    return (
        "Vibe Loop state restored.\n"
        f"Project root: {root}\n"
        f"Phase: {state.get('phase')}\n"
        f"Task: {state.get('task_id') or '-'}\n"
        f"Run status: {state.get('status')}\n"
        f"Native Goal: {state.get('native_goal', {}).get('last_known_status') or state.get('native_goal', {}).get('binding_status')}\n\n"
        f"{handoff}"
    )
