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
    # A Windows console defaults to a legacy codepage (for example cp1252); printing this
    # hook's non-ASCII JSON output there raises UnicodeEncodeError. The output contract is
    # UTF-8 on every platform, so force the process streams before anything is printed.
    # Only stdout/stderr are touched, never stdin, so the hook's stdin JSON protocol is
    # unchanged. The getattr check tolerates a harness with no reconfigure().
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
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
