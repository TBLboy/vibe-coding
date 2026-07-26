#!/usr/bin/env python3
"""Initialize or restore Vibe state and inject a compact session summary."""
from __future__ import annotations

import json

from hook_common import compact_context, ensure_project, maybe_probe, read_input


def main() -> int:
    payload = read_input()
    root = ensure_project(payload)
    maybe_probe(root, "SessionStart", payload)
    print(json.dumps({"additionalContext": compact_context(root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
