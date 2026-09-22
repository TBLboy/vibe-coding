#!/usr/bin/env python3
"""Command-line controller for the Vibe Loop Core."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

from loop_state import (
    append_event,
    apply_decision,
    evaluate_goal,
    generate_handoff,
    initialize_loop,
    invalidate_evidence,
    load_active_run,
    load_yaml,
    normalize_project_path,
    PHASES,
    project_goal_summary,
    project_log,
    read_events,
    record_evidence,
    restore_active_run,
    save_active_run,
    start_run,
    sync_native_goal,
    validate_loop,
    version_binding,
)

from framework_info import LEGACY_GUIDANCE, LEGACY_WRITE_WARNING

# Format 1 stays writable only during the migration window; every write has to
# announce the deprecation (contract section 6.2). Read-only commands do not.
LEGACY_WRITE_COMMANDS = {
    "init",
    "start-run",
    "decide",
    "record-evidence",
    "invalidate-evidence",
    "goal-bind",
    "goal-sync",
    "record-event",
    "handoff",
}


def output(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif isinstance(data, str):
        print(data, end="" if data.endswith("\n") else "\n")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_json(value: str) -> dict:
    path = Path(value)
    text = path.read_text(encoding="utf-8") if path.is_file() else value
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON payload must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init")
    commands.add_parser("restore")
    commands.add_parser("status")
    commands.add_parser("validate")
    commands.add_parser("handoff")

    start = commands.add_parser("start-run")
    start.add_argument("--phase", choices=sorted(PHASES), default="business-intent")
    start.add_argument("--task-id")

    bind = commands.add_parser("goal-bind")
    bind.add_argument("--native-id")

    sync = commands.add_parser("goal-sync")
    sync.add_argument("--status", required=True)
    sync.add_argument("--native-id")

    event = commands.add_parser("record-event")
    event.add_argument("--type", required=True)
    event.add_argument("--payload-json", default="{}")

    evidence = commands.add_parser("record-evidence")
    evidence.add_argument("--id", required=True)
    evidence.add_argument("--kind", required=True)
    evidence.add_argument("--subject", required=True)
    evidence.add_argument("--status", required=True)
    evidence.add_argument("--file", action="append", default=[])
    evidence.add_argument("--requirement", action="append", default=[])
    evidence.add_argument("--task", action="append", default=[])
    evidence.add_argument("--command-line")
    evidence.add_argument("--result-ref")
    evidence.add_argument("--replace", action="store_true")

    invalidate = commands.add_parser("invalidate-evidence")
    invalidate.add_argument("--path", action="append", default=[])
    invalidate.add_argument("--reason", required=True)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("scope", choices=("goal",))

    decide = commands.add_parser("decide")
    decide.add_argument("--decision-json", required=True)

    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    try:
        from state_context import is_transactional, open_store, refresh_views

        if is_transactional(root):
            if args.command in {"restore", "status"}:
                output(open_store(root, heal=True).status(), args.json)
            elif args.command == "validate":
                errors = open_store(root).validate()
                output({"errors": errors}, args.json)
                return int(bool(errors))
            elif args.command == "handoff":
                output(refresh_views(root), args.json)
            elif args.command == "evaluate":
                store = open_store(root, heal=True)
                output(store.evaluate_goal(store.active_goal_id()), args.json)
            elif args.command == "record-evidence":
                store = open_store(root, heal=True)
                payload = {
                    "id": args.id,
                    "kind": args.kind,
                    "subject": args.subject,
                    "status": args.status,
                    "covers": {
                        "files": args.file,
                        "requirements": args.requirement,
                        "tasks": args.task,
                    },
                    "version_binding": version_binding(root, args.file),
                }
                if len(args.task) == 1:
                    payload["task_id"] = args.task[0]
                output(store.apply({
                    "schema_version": 1,
                    "command_id": uuid.uuid4().hex,
                    "expected_revision": store.status()["revision"],
                    "action": "evidence.record",
                    "payload": payload,
                }), args.json)
            elif args.command == "invalidate-evidence":
                store = open_store(root)
                changed = {normalize_project_path(root, item) for item in args.path}
                invalidated = []
                for item in store.list_evidence():
                    if item["status"] not in {"candidate", "valid"}:
                        continue
                    covered = set(item.get("covers", {}).get("files", []))
                    if not covered.intersection(changed):
                        continue
                    if store.evidence_applicability(root, item)["applicability"] != "stale":
                        continue
                    store.apply({
                        "schema_version": 1,
                        "command_id": uuid.uuid4().hex,
                        "expected_revision": store.status()["revision"],
                        "action": "evidence.invalidate",
                        "payload": {"id": item["id"], "reason": args.reason},
                    })
                    invalidated.append(item["id"])
                output({"invalidated": invalidated}, args.json)
            elif args.command == "decide":
                raise ValueError(
                    "unsupported_legacy_command: use the native Goal/loop control surface for format 2"
                )
            elif args.command == "start-run":
                raise ValueError(
                    "unsupported_legacy_command: use vibe task begin --task-id ... --run-id ... --next-action ..."
                )
            elif args.command in {"goal-bind", "goal-sync", "record-event", "init"}:
                raise ValueError(
                    "unsupported_legacy_command: use the formal vibe command surface for format 2"
                )
            else:
                raise ValueError("unsupported_legacy_command: legacy writes disabled for format 2")
            return 0
        if args.command in LEGACY_WRITE_COMMANDS:
            print(f"[!] {LEGACY_WRITE_WARNING}", file=sys.stderr)
        if args.command == "init":
            output({"created": initialize_loop(root)}, args.json)
        elif args.command == "restore":
            active_missing = not (project_log(root) / "loop/active-run.yaml").is_file()
            created = initialize_loop(root)
            state, warnings = restore_active_run(root, force=active_missing)
            events, errors = read_events(root, tolerate_bad_tail=True)
            output(
                {
                    "created": created,
                    "state": state,
                    "event_count": len(events),
                    "warnings": warnings + errors,
                },
                args.json,
            )
        elif args.command == "status":
            state = load_active_run(root)
            goal = load_yaml(project_log(root) / "goals/active-goal.yaml").get("goal")
            evidence = load_yaml(project_log(root) / "loop/evidence-index.yaml").get("evidence", [])
            output(
                {
                    "format": 1,
                    "legacy": True,
                    "guidance": LEGACY_GUIDANCE,
                    "goal": goal,
                    "state": state,
                    "evidence_counts": {
                        status: sum(item.get("status") == status for item in evidence)
                        for status in ("candidate", "valid", "failed", "stale", "superseded", "invalid")
                    },
                },
                args.json,
            )
        elif args.command == "goal-bind":
            summary = project_goal_summary(root)
            if args.native_id:
                state = load_active_run(root)
                state["native_goal"]["binding_status"] = "bound"
                state["native_goal"]["thread_goal_id"] = args.native_id
                save_active_run(root, state)
                append_event(root, "native-goal-bound", {"thread_goal_id": args.native_id, "objective": summary})
            output({"objective": summary, "native_id": args.native_id}, args.json)
        elif args.command == "goal-sync":
            output(sync_native_goal(root, args.status, args.native_id), args.json)
        elif args.command == "record-event":
            output(append_event(root, args.type, parse_json(args.payload_json)), args.json)
        elif args.command == "record-evidence":
            output(
                record_evidence(
                    root,
                    evidence_id=args.id,
                    kind=args.kind,
                    subject=args.subject,
                    status=args.status,
                    files=args.file,
                    requirements=args.requirement,
                    tasks=args.task,
                    command=args.command_line,
                    result_ref=args.result_ref,
                    replace=args.replace,
                ),
                args.json,
            )
        elif args.command == "invalidate-evidence":
            output({"invalidated": invalidate_evidence(root, args.path, args.reason)}, args.json)
        elif args.command == "evaluate":
            output(evaluate_goal(root), args.json)
        elif args.command == "decide":
            output(apply_decision(root, parse_json(args.decision_json)), args.json)
        elif args.command == "handoff":
            output(generate_handoff(root), args.json)
        elif args.command == "start-run":
            initialize_loop(root)
            output(start_run(root, args.phase, args.task_id), args.json)
        elif args.command == "validate":
            errors = validate_loop(root)
            output(
                {
                    "format": 1,
                    "legacy": True,
                    "guidance": LEGACY_GUIDANCE,
                    "passed": not errors,
                    "errors": errors,
                },
                args.json,
            )
            return 1 if errors else 0
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[X] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
