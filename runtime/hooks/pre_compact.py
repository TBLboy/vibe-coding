#!/usr/bin/env python3
"""Generate a durable handoff before context compaction."""
from __future__ import annotations

import json
import sys

from hook_common import compact_context, ensure_project, read_input


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
    try:
        payload = read_input()
        root = ensure_project(payload)
        context = compact_context(root, refresh_handoff=True)
    except Exception as exc:
        context = f"Vibe state unavailable: {type(exc).__name__}: {exc}"
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreCompact",
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
