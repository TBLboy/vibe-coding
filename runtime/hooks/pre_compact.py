#!/usr/bin/env python3
"""Generate a durable handoff before context compaction."""
from __future__ import annotations

import json

from hook_common import compact_context, ensure_project, maybe_probe, read_input


def main() -> int:
    payload = read_input()
    root = ensure_project(payload)
    maybe_probe(root, "PreCompact", payload)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreCompact",
                    "additionalContext": compact_context(root),
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
