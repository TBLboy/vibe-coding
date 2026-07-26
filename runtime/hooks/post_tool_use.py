#!/usr/bin/env python3
"""Record tool completion and invalidate evidence covered by changed paths."""
from __future__ import annotations

import json
import sys

from hook_common import ensure_project, extract_paths, maybe_probe, read_input, tool_name

SCRIPTS = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from loop_state import append_event, invalidate_evidence


WRITE_TOOL_HINTS = ("apply_patch", "edit", "write", "shell", "exec", "command")


def main() -> int:
    payload = read_input()
    root = ensure_project(payload)
    maybe_probe(root, "PostToolUse", payload)
    name = tool_name(payload)
    paths = extract_paths(payload)
    invalidated: list[str] = []
    if paths and any(hint in name.lower() for hint in WRITE_TOOL_HINTS):
        invalidated = invalidate_evidence(root, paths, f"PostToolUse:{name}")
    append_event(
        root,
        "work-unit-finished",
        {
            "tool_name": name,
            "changed_paths": paths,
            "invalidated_evidence": invalidated,
        },
    )
    print(json.dumps({}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
