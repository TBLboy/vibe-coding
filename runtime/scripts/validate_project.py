#!/usr/bin/env python3
"""Validate a Project Log format 2 store: layout, gates and payload boundaries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def layout_errors(root: Path) -> list[str]:
    """A Project Log must live in a plain work folder (BL-LAYOUT-001 / BL-LAYOUT-002).

    ``init`` already refuses an unsupported layout, but ``validate`` is what catches a
    log that later drifted there — a directory copy, a manual move, or a work tree
    that was turned into a Git repository after the fact.
    """
    from state_context import detect_layout

    if not (root / ".project-log").exists():
        return []  # not a Project Log root here; the caller reports that separately
    layout = detect_layout(root)
    if layout == "plain_work_folder":
        return []
    return [
        f"unsupported work layout ({layout}): the Project Log must live in a plain work "
        "folder that is neither a Git worktree root nor inside one; see docs/TERMINOLOGY.md"
    ]


def validate(root: Path) -> list[str]:
    from state_context import is_transactional, open_store
    from state_store import StateError

    layout = layout_errors(root)
    if layout:
        return layout

    if not is_transactional(root):
        return [
            f"no Project Log format 2 found under {root}: expected "
            f"{root / '.project-log' / 'state-format.json'}"
        ]

    try:
        store = open_store(root)
    except (StateError, OSError, ValueError) as exc:
        return [str(exc)]
    # Collect every diagnostic instead of stopping at the first: a store with
    # ledger drift can still expose actionable gate or payload problems, and
    # the earlier short-circuit hid them behind a generic integrity error.
    errors: list[str] = []
    for check in (
        store.validate,
        store.audit_gates,
        lambda: transactional_record_errors(store),
        lambda: migration_state_errors(root),
    ):
        try:
            errors.extend(check())
        except (StateError, OSError, ValueError) as exc:
            errors.append(str(exc))
    return list(dict.fromkeys(errors))


def transactional_record_errors(store) -> list[str]:
    """Validate payload boundaries and human-readable IDs for format 2 records."""
    errors: list[str] = []
    for record in store.list_records():
        payload = record["payload"]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 16384:
            errors.append(f"record {record['kind']}/{record['id']}: payload exceeds 16384 bytes")
        for problem in long_form_payload_errors(payload):
            errors.append(f"record {record['kind']}/{record['id']}: {problem}")
    return errors


def long_form_payload_errors(value, path: str = "payload") -> list[str]:
    """Reject long-form text at any depth, mirroring the write-path boundary.

    A stored record can also be tampered with outside the command surface, so the
    validator must apply the same rule to the bytes it finds, not only to writes.
    """
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(long_form_payload_errors(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(long_form_payload_errors(item, f"{path}[{index}]"))
    elif isinstance(value, str) and len(value.encode("utf-8")) > 4096:
        errors.append(f"{path} carries long-form text over 4096 bytes; store a doc_ref instead")
    return errors


def migration_state_errors(root: Path) -> list[str]:
    """Reject contradictory historical migration markers or failed journals."""
    errors: list[str] = []
    journal_path = root / ".project-log/.migration/journal.json"
    marker_path = root / ".project-log/state-format.json"
    if not journal_path.is_file():
        return errors
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"migration journal is unreadable: {exc}"]
    status = journal.get("status")
    if status == "failed":
        errors.append(f"migration journal records a failed switch: {journal.get('error', 'unknown error')}")
    if status == "switched" and not marker_path.is_file():
        errors.append("migration journal says switched but state-format.json is missing")
    if marker_path.is_file() and status != "switched":
        errors.append(f"format 2 marker exists but migration journal status is {status!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    errors = validate(root)
    if errors:
        print(f"Validation failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Validation passed: the Project Log format 2 store, gates and payload boundaries are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
