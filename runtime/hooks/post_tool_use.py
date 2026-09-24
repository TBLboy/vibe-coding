#!/usr/bin/env python3
"""Record tool completion and invalidate evidence covered by changed paths."""
from __future__ import annotations

import json
import sys

from hook_common import ensure_project, extract_paths, read_input, tool_name

SCRIPTS = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


WRITE_TOOL_HINTS = ("apply_patch", "edit", "write", "shell", "exec", "command")


def main() -> int:
    payload = read_input()
    root = ensure_project(payload)
    from state_context import is_transactional

    if not is_transactional(root):
        print(json.dumps({}))
        return 0
    name = tool_name(payload)
    paths = extract_paths(payload)
    if paths and any(hint in name.lower() for hint in WRITE_TOOL_HINTS):
        try:
            from state_context import refresh_evidence

            result = refresh_evidence(root, f"PostToolUse:{name}", paths)
        except Exception as exc:  # hooks must not block the user's tool call
            print(f"Vibe PostToolUse state error: {type(exc).__name__}: {exc}", file=sys.stderr)
        else:
            if result.get("invalidated"):
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": (
                            "Vibe evidence invalidated: "
                            + ", ".join(result["invalidated"])
                        ),
                    }
                }, ensure_ascii=False))
                return 0
    print(json.dumps({}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
