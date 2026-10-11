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
    """Attach the transactional store, creating it when the directory has none.

    Format 2 is the only supported layout, so there is no legacy fallback: a directory
    without a Project Log gets a fresh format 2 store, and a directory that already has
    one is used as-is.
    """
    root = explicit_project_root(payload) or find_project_root(candidate_cwd(payload))
    from state_context import is_transactional

    if is_transactional(root):
        return root
    if not (root / ".project-log").is_dir():
        initialize_project(root)
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
    """Debug aid: `VIBE_HOOK_PROBE=1` appends raw hook payloads under the store state dir.

    The samples live inside `.project-log/.state/` so a probe run never pollutes the
    tracked Project Log.
    """
    if os.environ.get("VIBE_HOOK_PROBE") != "1":
        return
    path = root / ".project-log" / ".state" / "hook-samples.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"hook": hook_name, "payload": payload}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def compact_context(root: Path, refresh_handoff: bool = False) -> str:
    """Restore the transactional (format 2) context, optionally refreshing the views.

    Format 2 is the only supported layout; a directory without a store gets an explicit
    "no store attached" note instead of a legacy fallback.
    """
    from state_context import compact_context as transactional_context, is_transactional, refresh_views

    if not is_transactional(root):
        return (
            "Vibe transactional context (read-only restore).\n"
            f"Project root: {root}\n"
            "No format 2 store is attached. The user's newest request is authoritative. "
            "For a substantive new task, initialize the project log and create a new run.\n"
        )
    if refresh_handoff:
        refresh_views(root)
    return transactional_context(root)
