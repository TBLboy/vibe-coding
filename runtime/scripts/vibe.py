#!/usr/bin/env python3
"""Small local utilities for the Vibe Workflow project log."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print("Install dependencies: python -m pip install -r scripts/requirements.txt", file=sys.stderr)
    raise SystemExit(2) from exc

from framework_info import DEFAULT_FORMAT, LEGACY_GUIDANCE, VERSION, version_payload


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
    print("Format:      1 (legacy)")
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
    print(f"\nNote:        {LEGACY_GUIDANCE}")
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


def _json_argument(value: str | None, name: str):
    if value is None:
        return None
    if value.startswith("@"):
        try:
            text = Path(value[1:]).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"{name} file is unreadable: {exc}") from exc
    else:
        text = value
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be valid JSON") from exc


def apply_cli_action(root: Path, action: str, payload: dict) -> dict:
    from state_context import apply_command, open_store
    from state_store import SCHEMA_VERSION

    store = open_store(root)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command_id": uuid.uuid4().hex,
        "expected_revision": store.status()["revision"],
        "action": action,
        "payload": payload,
    }
    return apply_command(root, envelope)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--version",
        action="version",
        version=f"vibe-coding {VERSION} (default format {DEFAULT_FORMAT})",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the release identity, format policy and retirement stages")
    sub.add_parser("status")
    sub.add_parser("validate")
    sub.add_parser("render-tasks")
    sub.add_parser("render")
    init = sub.add_parser("init", help="create .project-log in format 2 (the default format)")
    init.add_argument("--dry-run", action="store_true")
    state_init = sub.add_parser("state-init", help="alias of init; --experimental is accepted and ignored")
    state_init.add_argument("--dry-run", action="store_true")
    state_init.add_argument("--experimental", action="store_true", help=argparse.SUPPRESS)
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
    task = sub.add_parser("task", help="manage transactional task lifecycle")
    task_sub = task.add_subparsers(dest="task_action", required=True)
    task_begin = task_sub.add_parser("begin")
    task_begin.add_argument("--task-id", required=True)
    task_begin.add_argument("--run-id", required=True)
    task_begin.add_argument("--next-action", required=True)
    task_update = task_sub.add_parser("update", help="record task attribution (implementer/owner)")
    task_update.add_argument("--task-id", required=True)
    task_update.add_argument("--implementer")
    task_update.add_argument("--owner")
    task_wait = task_sub.add_parser("wait")
    task_wait.add_argument("--task-id", required=True)
    task_wait.add_argument("--kind", required=True, choices=("user", "dependency", "environment"))
    task_wait.add_argument("--reason", required=True)
    task_wait.add_argument("--resume-when", required=True)
    task_wait.add_argument("--question-ref")
    task_resume = task_sub.add_parser("resume")
    task_resume.add_argument("--task-id", required=True)
    task_resume.add_argument("--next-action", required=True)
    task_handoff = task_sub.add_parser("handoff")
    task_handoff.add_argument("--task-id", required=True)
    task_handoff.add_argument("--next-action", required=True)
    task_finish = task_sub.add_parser("finish")
    task_finish.add_argument("--task-id", required=True)
    task_finish.add_argument("--summary", required=True)
    task_cancel = task_sub.add_parser("cancel")
    task_cancel.add_argument("--task-id", required=True)
    task_cancel.add_argument("--reason", required=True)
    route = sub.add_parser("route", help="classify task risk")
    route.add_argument("--path", action="append", default=[])
    route.add_argument("--signal", action="append", default=[])
    route.add_argument("--files-touched", type=int)
    route.add_argument("--irreversible", action="store_true")
    context = sub.add_parser("context", help="read bounded task context")
    context.add_argument("task_id")
    context.add_argument("--budget-bytes", type=int, default=4096)
    exchange = sub.add_parser("exchange", help="manage Git snapshot exchange")
    exchange_sub = exchange.add_subparsers(dest="exchange_action", required=True)
    exchange_sub.add_parser("status")
    exchange_sub.add_parser("export")
    exchange_sub.add_parser("import")
    exchange_sub.add_parser("finish")
    exchange_abandon = exchange_sub.add_parser("abandon")
    exchange_abandon.add_argument("--reason", required=True)
    ledger = sub.add_parser("ledger", help="manage the Git-tracked Format 3 ledger")
    ledger_sub = ledger.add_subparsers(dest="ledger_action", required=True)
    ledger_sub.add_parser("export")
    ledger_sub.add_parser("verify")
    migrate = sub.add_parser("migrate", help="manage legacy format migration")
    migrate_sub = migrate.add_subparsers(dest="migrate_action", required=True)
    migrate_sub.add_parser("preview")
    migrate_rollback = migrate_sub.add_parser("rollback")
    migrate_rollback.add_argument("--destination")
    migrate_apply = migrate_sub.add_parser("apply")
    migrate_apply.add_argument("--confirm", required=True)
    migrate_sub.add_parser("resume")
    record = sub.add_parser("record", help="manage lifecycle records")
    record_sub = record.add_subparsers(dest="record_action", required=True)
    record_create = record_sub.add_parser("create")
    record_create.add_argument("--kind", required=True)
    record_create.add_argument("--id", required=True)
    record_create.add_argument("--title", required=True)
    record_create.add_argument("--status", required=True)
    record_create.add_argument("--payload", help="JSON object; @file reads from disk")
    record_update = record_sub.add_parser("update")
    record_update.add_argument("--kind", required=True)
    record_update.add_argument("--id", required=True)
    record_update.add_argument("--expected-record-revision", required=True, type=int)
    record_update.add_argument("--status")
    record_update.add_argument("--payload", help="JSON object merged into the existing payload; @file reads from disk")
    record_link = record_sub.add_parser("link")
    record_link.add_argument("--from-kind", required=True)
    record_link.add_argument("--from-id", required=True)
    record_link.add_argument("--relation", required=True)
    record_link.add_argument("--to-kind", required=True)
    record_link.add_argument("--to-id", required=True)
    evidence = sub.add_parser("evidence", help="manage transactional evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_action", required=True)
    evidence_record = evidence_sub.add_parser("record")
    evidence_record.add_argument("--id", required=True)
    evidence_record.add_argument("--kind", required=True)
    evidence_record.add_argument("--subject", required=True)
    evidence_record.add_argument("--status", required=True)
    evidence_record.add_argument("--task-id")
    evidence_record.add_argument("--covers", help="JSON object; @file reads from disk")
    evidence_record.add_argument("--version-binding", help="JSON object; @file reads from disk")
    evidence_invalidate = evidence_sub.add_parser("invalidate")
    evidence_invalidate.add_argument("--id", required=True)
    evidence_invalidate.add_argument("--reason", required=True)
    evidence_refresh = evidence_sub.add_parser("refresh")
    evidence_refresh.add_argument("--reason")
    goal = sub.add_parser("goal", help="manage the active project goal")
    goal_sub = goal.add_subparsers(dest="goal_action", required=True)
    goal_update = goal_sub.add_parser("update", help="record success-condition progress")
    goal_update.add_argument("--id", required=True)
    goal_update.add_argument("--success-conditions", help="JSON list; @file reads from disk")
    goal_update.add_argument("--required-evidence", help="JSON list; @file reads from disk")
    goal_complete = goal_sub.add_parser("complete")
    goal_complete.add_argument("--id", required=True)
    gate = sub.add_parser("gate", help="evaluate a task completion gate")
    gate.add_argument("--task", required=True)
    review = sub.add_parser("review", help="manage transactional reviews")
    review_sub = review.add_subparsers(dest="review_action", required=True)
    review_record = review_sub.add_parser("record")
    review_record.add_argument("--id", required=True)
    review_record.add_argument("--task-id", required=True)
    review_record.add_argument("--reviewer", required=True)
    review_record.add_argument("--verdict", required=True)
    review_record.add_argument("--scope", required=True, help="JSON object; @file reads from disk")
    review_record.add_argument("--evidence-ref", action="append", default=[])
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
    from state_migrate import apply as migration_apply
    from state_migrate import resume as migration_resume
    from state_migrate import rollback as migration_rollback
    from state_migrate import rollback_bundle
    from state_store import StateError

    try:
        result = None
        if args.command == "version":
            result = version_payload()
        elif args.command in {"init", "state-init"}:
            from init_project import initialize_project

            created, skipped = initialize_project(root, args.dry_run)
            result = {
                "format": 2,
                "dry_run": args.dry_run,
                "created": [str(item) for item in created],
                "skipped": [str(item) for item in skipped],
            }
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
        elif args.command == "task":
            if args.task_action == "begin":
                result = apply_cli_action(root, "task.begin", {
                    "task_id": args.task_id, "run_id": args.run_id,
                    "next_action": args.next_action,
                })
            elif args.task_action == "update":
                payload = {"task_id": args.task_id}
                if args.implementer is not None:
                    payload["implementer"] = args.implementer
                if args.owner is not None:
                    payload["owner"] = args.owner
                result = apply_cli_action(root, "task.update", payload)
            elif args.task_action == "wait":
                payload = {
                    "task_id": args.task_id, "kind": args.kind,
                    "reason": args.reason, "resume_when": args.resume_when,
                }
                if args.question_ref is not None:
                    payload["question_ref"] = args.question_ref
                result = apply_cli_action(root, "task.wait", payload)
            elif args.task_action == "resume":
                result = apply_cli_action(root, "task.resume", {
                    "task_id": args.task_id, "next_action": args.next_action,
                })
            elif args.task_action == "handoff":
                result = apply_cli_action(root, "task.handoff", {
                    "task_id": args.task_id, "next_action": args.next_action,
                })
            elif args.task_action == "finish":
                result = apply_cli_action(root, "task.finish", {
                    "task_id": args.task_id, "summary": args.summary,
                })
            else:
                result = apply_cli_action(root, "task.cancel", {
                    "task_id": args.task_id, "reason": args.reason,
                })
        elif args.command == "route":
            result = route(args.path, args.signal or None, args.files_touched, not args.irreversible)
        elif args.command == "context":
            result = task_context(open_store(root), args.task_id, args.budget_bytes)
        elif args.command == "exchange":
            if args.exchange_action == "status":
                result = exchange_status(root)
            elif args.exchange_action == "export":
                result = publish_snapshot(root)
            elif args.exchange_action == "import":
                result = import_snapshot(root)
            elif args.exchange_action == "finish":
                result = acknowledge_export(root)
            else:
                result = abandon_export(root, args.reason)
        elif args.command == "ledger":
            from state_ledger import export_ledger, verify_ledger

            if args.ledger_action == "export":
                result = export_ledger(open_store(root))
            else:
                result = verify_ledger(root)
        elif args.command == "migrate":
            if args.migrate_action == "preview":
                result = migration_preview(root)
            elif args.migrate_action == "apply":
                result = migration_apply(root, args.confirm)
            elif args.migrate_action == "resume":
                result = migration_resume(root)
            else:
                result = migration_rollback(root, args.destination)
        elif args.command == "render":
            result = refresh_views(root)
        elif args.command == "record":
            if args.record_action == "create":
                payload = {
                    "kind": args.kind, "id": args.id, "title": args.title,
                    "status": args.status,
                }
                parsed = _json_argument(args.payload, "payload")
                if parsed is not None:
                    payload["payload"] = parsed
                result = apply_cli_action(root, "record.create", payload)
            elif args.record_action == "update":
                payload = {
                    "kind": args.kind, "id": args.id,
                    "expected_record_revision": args.expected_record_revision,
                }
                if args.status is not None:
                    payload["status"] = args.status
                parsed = _json_argument(args.payload, "payload")
                if parsed is not None:
                    payload["payload"] = parsed
                result = apply_cli_action(root, "record.update", payload)
            else:
                result = apply_cli_action(root, "record.link", {
                    "from_kind": args.from_kind, "from_id": args.from_id,
                    "relation": args.relation, "to_kind": args.to_kind, "to_id": args.to_id,
                })
        elif args.command == "evidence":
            if args.evidence_action == "record":
                payload = {
                    "id": args.id, "kind": args.kind, "subject": args.subject,
                    "status": args.status,
                }
                if args.task_id is not None:
                    payload["task_id"] = args.task_id
                covers = _json_argument(args.covers, "covers")
                if covers is not None:
                    payload["covers"] = covers
                binding = _json_argument(args.version_binding, "version_binding")
                if binding is not None:
                    payload["version_binding"] = binding
                result = apply_cli_action(root, "evidence.record", payload)
            elif args.evidence_action == "invalidate":
                result = apply_cli_action(root, "evidence.invalidate", {
                    "id": args.id, "reason": args.reason,
                })
            else:
                from state_context import refresh_evidence

                result = refresh_evidence(root, args.reason)
        elif args.command == "goal":
            if args.goal_action == "update":
                payload = {"id": args.id}
                conditions = _json_argument(args.success_conditions, "success_conditions")
                if conditions is not None:
                    payload["success_conditions"] = conditions
                required = _json_argument(args.required_evidence, "required_evidence")
                if required is not None:
                    payload["required_evidence"] = required
                result = apply_cli_action(root, "goal.update", payload)
            else:
                result = apply_cli_action(root, "goal.complete", {"id": args.id})
        elif args.command == "gate":
            result = open_store(root).gate_task(args.task)
        elif args.command == "review":
            result = apply_cli_action(root, "review.record", {
                "id": args.id, "task_id": args.task_id, "reviewer": args.reviewer,
                "verdict": args.verdict, "scope": _json_argument(args.scope, "scope"),
                "evidence_refs": args.evidence_ref,
            })
        elif is_transactional(root):
            if args.command == "status":
                result = open_store(root).status()
            elif args.command == "validate":
                errors = open_store(root).validate()
                print(json.dumps({"errors": errors}, ensure_ascii=True))
                return int(bool(errors))
            else:
                raise StateError(
                    "unsupported_legacy_command",
                    "legacy writes are disabled for format 2; use the formal vibe command surface",
                )
        elif args.command in {"status", "validate", "render-tasks", "next-id"}:
            # Not a format 2 project. The legacy fallback below needs a legacy
            # Project Log; report a clean error instead of a traceback when the
            # directory holds no Vibe project at all.
            if not (root / ".project-log" / "workflow.yaml").exists():
                raise StateError(
                    "not_a_project",
                    f"No Vibe Project Log found under {root}: expected "
                    f"{(root / '.project-log' / 'state-format.json')} (format 2) or "
                    f"{(root / '.project-log' / 'workflow.yaml')} (format 1). "
                    "Run 'vibe init' to create a format 2 project.",
                )
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
