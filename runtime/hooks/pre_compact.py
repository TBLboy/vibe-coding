#!/usr/bin/env python3
"""Generate a durable handoff before context compaction."""
from __future__ import annotations

import json

from hook_common import compact_context, ensure_project, read_input


def main() -> int:
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
