#!/usr/bin/env python3
"""Small local utilities for the Vibe Workflow project log."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print("Install dependencies: python -m pip install -r scripts/requirements.txt", file=sys.stderr)
    raise SystemExit(2) from exc


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def status(root: Path) -> int:
    workflow = load(root / ".project-log/workflow.yaml")
    tasks = load(root / ".project-log/tasks/task-list.yaml").get("tasks", [])
    atoms = load(root / ".project-log/business-logic/atoms.yaml").get("atoms", [])
    findings = load(root / ".project-log/alignment/findings.yaml").get("findings", [])
    questions = load(root / ".project-log/business-logic/open-questions.yaml").get("questions", [])
    goal = load(root / ".project-log/goals/active-goal.yaml").get("goal")
    loop = load(root / ".project-log/loop/active-run.yaml")
    evidence = load(root / ".project-log/loop/evidence-index.yaml").get("evidence", [])

    active_tasks = [t for t in tasks if t.get("status") in {"ready", "in-progress", "blocked", "implemented-unverified"}]
    print(f"Phase:       {workflow.get('current_phase')}")
    print(f"Mode:        {workflow.get('mode')}")
    print(f"Active goal: {(goal or {}).get('id') or workflow.get('active_goal') or '-'}")
    print(f"Run status:  {loop.get('status')}")
    print(f"Native Goal: {loop.get('native_goal', {}).get('last_known_status') or loop.get('native_goal', {}).get('binding_status')}")
    print(f"Atoms:       {len(atoms)} total, {sum(a.get('status') == 'active' for a in atoms)} active")
    print(f"Tasks:       {len(tasks)} total, {len(active_tasks)} active/blocked")
    print(f"Findings:    {sum(f.get('status') in {'open','accepted','in-progress'} for f in findings)} unresolved")
    print(f"C questions: {sum(q.get('status') == 'open' and q.get('authority') == 'C' for q in questions)} open")
    print(f"Evidence:    {sum(item.get('status') == 'valid' for item in evidence)} valid, {sum(item.get('status') == 'stale' for item in evidence)} stale")
    if active_tasks:
        print("\nCurrent tasks:")
        for task in active_tasks:
            print(f"- {task['id']} [{task['status']}] {task['title']}")
    return 0


def render_tasks(root: Path) -> int:
    from state_context import reject_legacy

    reject_legacy(root)
    source = root / ".project-log/tasks/task-list.yaml"
    destination = root / ".project-log/tasks/task-list.md"
    data = load(source)
    tasks = data.get("tasks", [])
    lines = ["# Task List", "", f"Active goal: {data.get('active_goal') or '-'}", ""]
    if not tasks:
        lines.append("No tasks.")
    else:
        phases: dict[str, list[dict]] = {}
        for task in tasks:
            phases.setdefault(task["phase"], []).append(task)
        for phase, phase_tasks in phases.items():
            lines.extend([f"## {phase}", "", "| ID | Status | Kind | Priority | Title |", "|---|---|---|---|---|"])
            for task in phase_tasks:
                lines.append(f"| {task['id']} | {task['status']} | {task['kind']} | {task.get('priority','-')} | {task['title']} |")
            lines.append("")
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(destination)
    return 0


def next_id(root: Path, kind: str) -> int:
    mapping = {
        "task": (".project-log/tasks/task-list.yaml", "tasks", "TASK"),
        "logic": (".project-log/business-logic/atoms.yaml", "atoms", "BL-GEN"),
        "decision": (".project-log/decisions/decision-log.yaml", "decisions", "DEC"),
        "alignment": (".project-log/alignment/findings.yaml", "findings", "ALN"),
        "knowledge": (".project-log/distillation/candidates.yaml", "candidates", "KNOW"),
        "question": (".project-log/business-logic/open-questions.yaml", "questions", "Q"),
    }
    rel, key, prefix = mapping[kind]
    items = load(root / rel).get(key, [])
    numbers = []
    pattern = re.compile(r"(\d+)$")
    for item in items:
        match = pattern.search(str(item.get("id", "")))
        if match:
            numbers.append(int(match.group(1)))
    print(f"{prefix}-{max(numbers, default=0) + 1:03d}")
    return 0


def run_validate(root: Path) -> int:
    script = Path(__file__).with_name("validate_project.py")
    return subprocess.call([sys.executable, str(script), "--root", str(root)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("validate")
    sub.add_parser("render-tasks")
    state_init = sub.add_parser("state-init", help="experimental new-fixture-only initialization")
    state_init.add_argument("--experimental", action="store_true", required=True)
    state_apply = sub.add_parser("state-apply")
    state_apply.add_argument("--file", required=True, help="UTF-8 command envelope file, or - for stdin")
    state_task = sub.add_parser("state-task")
    state_task.add_argument("task_id")
    sub.add_parser("state-views")
    sub.add_parser("state-attach")
    sub.add_parser("state-export")
    sub.add_parser("state-import")
    sub.add_parser("state-exchange")
    sub.add_parser("state-exchange-finish")
    state_abandon = sub.add_parser("state-exchange-abandon")
    state_abandon.add_argument("--reason", required=True)
    state_route = sub.add_parser("state-route")
    state_route.add_argument("--path", action="append", default=[])
    state_route.add_argument("--signal", action="append", default=[])
    state_route.add_argument("--files-touched", type=int)
    state_route.add_argument("--irreversible", action="store_true")
    state_context_parser = sub.add_parser("state-context")
    state_context_parser.add_argument("task_id")
    state_context_parser.add_argument("--budget-bytes", type=int, default=4096)
    state_fingerprint = sub.add_parser("state-fingerprint")
    state_fingerprint.add_argument("--path", required=True)
    state_fingerprint.add_argument("--selector", choices=["raw-file", "text-lf", "json-field"], default="raw-file")
    state_fingerprint.add_argument("--field")
    state_evidence = sub.add_parser("state-evidence-check")
    state_evidence.add_argument("--file", required=True, help="UTF-8 JSON evidence record")
    state_gate = sub.add_parser("state-gate")
    state_gate.add_argument("--file", required=True, help="UTF-8 JSON list of evidence records")
    state_gate.add_argument("--task")
    state_gate.add_argument("--risk-class", choices=["quick", "standard", "strict"])
    state_invalidate = sub.add_parser("state-gate-invalidate")
    state_invalidate.add_argument("--file", required=True, help="UTF-8 JSON list of evidence records")
    state_invalidate.add_argument("--changed", action="append", default=[])
    sub.add_parser("state-migrate-preview")
    state_rollback = sub.add_parser("state-migrate-rollback")
    state_rollback.add_argument("--destination", required=True)
    next_parser = sub.add_parser("next-id")
    next_parser.add_argument("kind", choices=["task", "logic", "decision", "alignment", "knowledge", "question"])
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    from state_context import (
        apply_command,
        attach,
        exchange_status,
        acknowledge_export,
        abandon_export,
        import_snapshot,
        initialize,
        is_transactional,
        open_store,
        publish_snapshot,
        refresh_views,
    )
    from state_routing import context as task_context
    from state_routing import route
    from state_evidence import applicability, fingerprint_file
    from state_gate import gate as evidence_gate
    from state_gate import invalidate as evidence_invalidate
    from state_migrate import preview as migration_preview
    from state_migrate import rollback_bundle
    from state_store import StateError

    try:
        result = None
        if args.command == "state-init":
            result = initialize(root).status()
        elif args.command == "state-apply":
            if args.file == "-":
                text = sys.stdin.read(65537)
            else:
                with Path(args.file).open(encoding="utf-8") as stream:
                    text = stream.read(65537)
            if len(text) > 65536:
                raise StateError("invalid_input", "command envelope exceeds 65536 characters")
            result = apply_command(root, json.loads(text))
        elif args.command == "state-task":
            result = open_store(root).get_task(args.task_id)
        elif args.command == "state-views":
            result = refresh_views(root)
        elif args.command == "state-attach":
            result = attach(root).status()
        elif args.command == "state-export":
            result = publish_snapshot(root)
        elif args.command == "state-import":
            result = import_snapshot(root)
        elif args.command == "state-exchange":
            result = exchange_status(root)
        elif args.command == "state-exchange-finish":
            result = acknowledge_export(root)
        elif args.command == "state-exchange-abandon":
            result = abandon_export(root, args.reason)
        elif args.command == "state-route":
            result = route(args.path, args.signal or None, args.files_touched, not args.irreversible)
        elif args.command == "state-context":
            result = task_context(open_store(root), args.task_id, args.budget_bytes)
        elif args.command == "state-fingerprint":
            result = fingerprint_file(args.path, args.selector, args.field)
        elif args.command == "state-evidence-check":
            with Path(args.file).open(encoding="utf-8") as stream:
                result = applicability(json.load(stream), root)
        elif args.command == "state-gate":
            with Path(args.file).open(encoding="utf-8") as stream:
                result = evidence_gate(json.load(stream), root, args.task, None, args.risk_class)
        elif args.command == "state-gate-invalidate":
            with Path(args.file).open(encoding="utf-8") as stream:
                result = evidence_invalidate(json.load(stream), args.changed, root)
        elif args.command == "state-migrate-preview":
            result = migration_preview(root)
        elif args.command == "state-migrate-rollback":
            result = rollback_bundle(open_store(root), root, args.destination)
        elif is_transactional(root):
            if args.command == "status":
                result = open_store(root).status()
            elif args.command == "validate":
                errors = open_store(root).validate()
                print(json.dumps({"errors": errors}, ensure_ascii=True))
                return int(bool(errors))
            else:
                raise StateError("unsupported_legacy_command", "use state-apply or state-views for format 2")
        if result is not None:
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0
    except (StateError, OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": getattr(exc, "code", "invalid_input"), "message": str(exc)}}, ensure_ascii=True), file=sys.stderr)
        return 2
    if args.command == "status":
        return status(root)
    if args.command == "validate":
        return run_validate(root)
    if args.command == "render-tasks":
        return render_tasks(root)
    if args.command == "next-id":
        return next_id(root, args.kind)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
