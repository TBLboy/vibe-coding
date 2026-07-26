#!/usr/bin/env python3
"""Command-line controller for the Vibe Loop Core."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from loop_state import (
    append_event,
    apply_decision,
    evaluate_goal,
    generate_handoff,
    initialize_loop,
    invalidate_evidence,
    load_active_run,
    load_yaml,
    project_goal_summary,
    project_log,
    read_events,
    record_evidence,
    restore_active_run,
    save_active_run,
    sync_native_goal,
    validate_loop,
)


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
        elif args.command == "validate":
            errors = validate_loop(root)
            output({"passed": not errors, "errors": errors}, args.json)
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
