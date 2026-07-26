#!/usr/bin/env python3
"""Render a bounded Vibe Coding role prompt for a native Codex subagent call."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, help="Role name from runtime/agents/roles.json")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--task", required=True, help="Precise delegated outcome")
    parser.add_argument("--scope", required=True, help="Allowed file/module scope or read-only boundary")
    parser.add_argument("--context-file", type=Path, help="Optional extra task context file")
    args = parser.parse_args()

    runtime = Path(__file__).resolve().parents[1]
    registry = json.loads((runtime / "agents" / "roles.json").read_text(encoding="utf-8"))
    roles = registry.get("roles", {})
    if args.role not in roles:
        parser.error("unknown role; choose: " + ", ".join(sorted(roles)))
    template = runtime / "agents" / f"{args.role}.md"
    if not template.is_file():
        parser.error(f"role template is missing: {template}")

    extra = ""
    if args.context_file:
        if not args.context_file.is_file():
            parser.error(f"context file does not exist: {args.context_file}")
        extra = "\n## Additional context\n\n" + args.context_file.read_text(encoding="utf-8").strip() + "\n"

    metadata = roles[args.role]
    write = "yes, only inside the assigned scope" if metadata.get("writes_product_code") else "no product-code writes"
    prompt = f'''# Delegated Vibe Coding subagent request

## Runtime contract

{template.read_text(encoding="utf-8").strip()}

## Assignment

- **Role:** `{args.role}`
- **Project root:** `{args.project_root.expanduser().resolve()}`
- **Task outcome:** {args.task}
- **Allowed scope:** {args.scope}
- **Product-code write policy:** {write}
- **Required Skill:** `{metadata.get("skill")}`

Do not expand scope, make C-level product decisions, overwrite unrelated user changes, or declare
unverified implementation complete. Return the six-part report required by the role contract.
{extra}'''
    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
