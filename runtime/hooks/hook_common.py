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
from loop_state import append_event, generate_handoff, initialize_loop, load_active_run, load_yaml, project_log


for _stream in (sys.stdin, sys.stdout):
    if _stream is not None:
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


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


def explicit_project_root(payload: dict[str, Any]) -> Path | None:
    for key in ("project_root", "workspace_root"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return Path(value).expanduser().resolve()
    return None


def find_project_root(start: Path) -> Path:
    """Only the current directory's Project Log counts; ancestors only contribute a Git root.

    Otherwise a brand-new directory inside an existing project would silently inherit the
    parent's Project Log instead of starting its own.
    """
    from state_context import is_transactional

    current = start if start.is_dir() else start.parent
    git_root: Path | None = None
    if is_transactional(current) or (current / ".project-log").is_dir():
        return current
    for candidate in (current, *current.parents):
        if git_root is None and (candidate / ".git").exists():
            git_root = candidate
    if git_root is not None:
        return git_root
    return current


def ensure_project(payload: dict[str, Any]) -> Path:
    root = explicit_project_root(payload) or find_project_root(candidate_cwd(payload))
    from state_context import is_transactional

    if is_transactional(root):
        return root
    if not project_log(root).is_dir():
        initialize_project(root)
    if is_transactional(root):
        # Format 2 is the default now: legacy loop files must not be created beside it.
        return root
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
    from state_context import is_transactional

    if is_transactional(root):
        return
    if os.environ.get("VIBE_HOOK_PROBE") != "1":
        return
    path = project_log(root) / "loop/hook-samples.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"hook": hook_name, "payload": payload}, ensure_ascii=False) + "\n")


def compact_context(root: Path, refresh_handoff: bool = False) -> str:
    from state_context import compact_context as transactional_context, is_transactional

    if is_transactional(root):
        if refresh_handoff:
            from state_context import refresh_views

            refresh_views(root)
        return transactional_context(root)
    state = load_active_run(root)
    if refresh_handoff:
        generate_handoff(root)
    goal = load_yaml(project_log(root) / "goals/active-goal.yaml").get("goal")
    status = state.get("status")
    has_active_work = bool(state.get("task_id") or state.get("next_action") or goal)
    if status == "active" and has_active_work:
        instruction = (
            "An unfinished Vibe run is active. Continue its concrete next action when it is relevant to "
            "the user's request; do not stop after reporting restored state."
        )
        display_status = status
    elif status == "handed-off" and has_active_work:
        instruction = (
            "A Vibe run is handed off. Read the recorded next action when it is relevant to the user's "
            "request; do not stop after reporting restored state."
        )
        display_status = status
    else:
        instruction = (
            "No active Vibe work is restored. The user's newest request is authoritative. For a substantive "
            "new task, create a new run before working. Do not reply with a restoration summary only."
        )
        display_status = "idle" if status == "active" else status
    return (
        "Vibe Loop context.\n"
        f"Project root: {root}\n"
        f"Phase: {state.get('phase')}\n"
        f"Active task: {state.get('task_id') if status in {'active', 'handed-off'} and has_active_work else '-'}\n"
        f"Run status: {display_status}\n"
        f"Project goal: {goal.get('id') if goal else '-'}\n"
        f"Native Goal: {state.get('native_goal', {}).get('last_known_status') or state.get('native_goal', {}).get('binding_status')}\n\n"
        f"{instruction}\n"
    )
