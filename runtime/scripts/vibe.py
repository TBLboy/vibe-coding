#!/usr/bin/env python3
"""Small local utilities for the Vibe Workflow project log."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from framework_info import DEFAULT_FORMAT, VERSION, version_payload


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

    # The CLI's own writes always start from a healed projection, so the
    # expected_revision it stamps is the revision the command will really apply on
    # top of. A crash between the ledger fsync and the SQLite commit must not make
    # the next `vibe task ...` fail with a stale revision the user cannot see.
    store = open_store(root, heal=True)
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
    sub.add_parser("version", help="print the release identity and the supported Project Log format")
    sub.add_parser("status")
    sub.add_parser("validate")
    sub.add_parser("render")
    init = sub.add_parser("init", help="create .project-log in format 2 (the only supported format)")
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
    state_evidence = sub.add_parser(
        "state-evidence-check",
        help="compare a recorded evidence record with the bytes it covers",
    )
    state_evidence.add_argument("--file", help="UTF-8 JSON evidence record")
    state_evidence.add_argument(
        "--id", help="id of a stored evidence record (alternative to --file)"
    )
    state_gate = sub.add_parser("state-gate")
    state_gate.add_argument("--file", required=True, help="UTF-8 JSON list of evidence records")
    state_gate.add_argument("--task")
    state_gate.add_argument("--risk-class", choices=["quick", "standard", "strict"])
    state_invalidate = sub.add_parser("state-gate-invalidate")
    state_invalidate.add_argument("--file", required=True, help="UTF-8 JSON list of evidence records")
    state_invalidate.add_argument("--changed", action="append", default=[])
    task = sub.add_parser("task", help="manage transactional task lifecycle")
    task_sub = task.add_subparsers(dest="task_action", required=True)
    task_create = task_sub.add_parser("create", help="create a task")
    task_create.add_argument("--id", required=True)
    task_create.add_argument("--title", required=True)
    task_create.add_argument("--goal-id", help="owning goal (omit for a goal-less task)")
    task_create.add_argument("--extensions", help="JSON object of task extensions")
    task_reopen = task_sub.add_parser(
        "reopen", help="start a new attempt at a finished or cancelled task")
    task_reopen.add_argument("--task-id", required=True)
    task_reopen.add_argument("--new-task-id", required=True)
    task_reopen.add_argument("--reason", required=True)
    task_reopen.add_argument("--title", help="title for the new task (default: the old one)")
    task_begin = task_sub.add_parser("begin")
    task_begin.add_argument("--task-id", required=True)
    task_begin.add_argument("--run-id", required=True)
    task_begin.add_argument("--next-action", required=True)
    task_begin.add_argument("--owner", required=True, help="immutable audit owner for this Run")
    task_begin.add_argument("--session-id", required=True, help="immutable OpenCode/session audit identifier")
    task_begin.add_argument(
        "--write-scope", required=True, action="append",
        help="literal project-relative product write root; repeat for disjoint roots",
    )
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
    memory = sub.add_parser("memory", help="Agent-maintained semantic project memory")
    memory_sub = memory.add_subparsers(dest="memory_action", required=True)
    memory_sub.add_parser("read", help="read current-session.md and progress.md with digests")
    memory_sync = memory_sub.add_parser("sync", help="atomically replace one or both notes")
    memory_sync.add_argument(
        "--file", required=True,
        help="JSON object with current_session and/or progress; prefix a path with @ to read it from disk",
    )
    ledger = sub.add_parser("ledger", help="manage the Git-tracked Project Log ledger")
    ledger_sub = ledger.add_subparsers(dest="ledger_action", required=True)
    ledger_sub.add_parser("export")
    ledger_sub.add_parser("verify")
    ledger_list = ledger_sub.add_parser("list", help="print recent ledger entries")
    ledger_list.add_argument("--limit", type=int, default=20)
    sub.add_parser("portability-status", help="report local consistency and remote durability separately")
    record = sub.add_parser("record", help="manage lifecycle records")
    record_sub = record.add_subparsers(dest="record_action", required=True)
    record_show = record_sub.add_parser("show", help="read one structured record")
    record_show.add_argument("--kind", help="record kind; inferred from the id when omitted")
    record_show.add_argument("--id", required=True)
    record_list = record_sub.add_parser("list", help="list persisted records")
    record_list.add_argument("--kind")
    record_list.add_argument("--limit", type=int, default=50)
    record_list.add_argument(
        "--full",
        action="store_true",
        help="include each record's payload (default: a kind/id/title/status projection)",
    )
    record_links = record_sub.add_parser("links", help="read record references")
    record_links.add_argument("--kind")
    record_links.add_argument("--id")
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
    evidence_record = evidence_sub.add_parser(
        "record",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""JSON shapes (each flag also accepts @file to read the JSON from disk):
  --covers           {"files": [path, ...], "requirements": [id, ...], "tasks": [id, ...]}
  --version-binding  {"git_commit": text|null, "diff_hash": text|null,
                      "file_hashes": {path: sha256}}

  --status is the historical result: candidate | valid | failed | stale | superseded | invalid.
  Applicability is derived from the covered bytes and is never written here.

Example:
  vibe evidence record --id E-1 --kind test --subject 'unit tests' --status valid --task-id T-1 --covers '{"files": ["a.py"], "tasks": ["T-1"]}'
""",
    )
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
    goal_create = goal_sub.add_parser("create", help="create a goal")
    goal_create.add_argument("--id", required=True)
    goal_create.add_argument("--title", required=True)
    goal_create.add_argument("--extensions", help="JSON object of goal extensions")
    goal_update = goal_sub.add_parser("update", help="record success-condition progress")
    goal_update.add_argument("--id", required=True)
    goal_update.add_argument("--success-conditions", help="JSON list; @file reads from disk")
    goal_update.add_argument("--required-evidence", help="JSON list; @file reads from disk")
    goal_update.add_argument("--implementer", help="who implemented the goal (attribution)")
    goal_update.add_argument("--owner", help="who owns the goal (attribution)")
    goal_complete = goal_sub.add_parser("complete")
    goal_complete.add_argument("--id", required=True)
    goal_cancel = goal_sub.add_parser("cancel", help="cancel a goal without a completion gate")
    goal_cancel.add_argument("--id", required=True)
    goal_cancel.add_argument("--reason", required=True)
    goal_cancel.add_argument("--child-policy", choices=["cancel_open", "keep"],
                             default="cancel_open")
    workspace = sub.add_parser("workspace", help="manage the active workspace generation")
    workspace_sub = workspace.add_subparsers(dest="workspace_action", required=True)
    workspace_clear = workspace_sub.add_parser(
        "clear", help="archive the active view and cancel its open work")
    workspace_clear.add_argument("--scope", choices=["active"], default="active")
    workspace_clear.add_argument("--reason", required=True)
    workspace_clear.add_argument("--dry-run", action="store_true",
                                 help="report the plan without writing anything")
    workspace_clear.add_argument("--expected-revision", type=int,
                                 help="the revision the plan was inspected at")
    workspace_clear.add_argument("--plan-digest",
                                 help="the plan_digest returned by --dry-run")
    workspace_sub.add_parser("status", help="show the current workspace generation")
    workspace_sub.add_parser("history", help="show every goal and task, cancelled included")
    verification = sub.add_parser(
        "verification", help="run project checks through the trusted action registry")
    verification_sub = verification.add_subparsers(
        dest="verification_action", required=True)
    for name, help_text in (
        ("preflight", "report whether an action can run here, before verification starts"),
        ("run", "execute one trusted action and print its VerificationRun"),
    ):
        item = verification_sub.add_parser(name, help=help_text)
        item.add_argument("--action", required=True, help="a trusted action id")
        item.add_argument("--path", help="file argument for actions that take one")
        item.add_argument("--timeout", type=int, default=900)
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
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    from state_context import (
        apply_command,
        attach_with_report,
        is_transactional,
        open_store,
        refresh_views,
    )
    from state_routing import context as task_context
    from state_routing import route
    from state_evidence import applicability, fingerprint_file
    from state_gate import gate as evidence_gate
    from state_gate import invalidate as evidence_invalidate
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
            result = open_store(root, heal=True).get_task(args.task_id)
        elif args.command == "state-views":
            result = refresh_views(root)
        elif args.command == "state-attach":
            store, report = attach_with_report(root)
            result = {"attach": report, "status": store.status()}
        elif args.command == "state-route":
            result = route(args.path, args.signal or None, args.files_touched, not args.irreversible)
        elif args.command == "state-context":
            result = task_context(open_store(root, heal=True), args.task_id, args.budget_bytes)
        elif args.command == "state-fingerprint":
            result = fingerprint_file(args.path, args.selector, args.field)
        elif args.command == "state-evidence-check":
            if (args.file is None) == (args.id is None):
                raise ValueError("pass exactly one of --file or --id")
            if args.id is not None:
                store = open_store(root, heal=True)
                result = store.evidence_applicability(root, store.get_evidence(args.id))
            else:
                with Path(args.file).open(encoding="utf-8") as stream:
                    result = applicability(json.load(stream), root)
        elif args.command == "state-gate":
            with Path(args.file).open(encoding="utf-8") as stream:
                result = evidence_gate(json.load(stream), root, args.task, None, args.risk_class)
        elif args.command == "state-gate-invalidate":
            with Path(args.file).open(encoding="utf-8") as stream:
                result = evidence_invalidate(json.load(stream), args.changed, root)
        elif args.command == "task":
            if args.task_action == "create":
                # `--goal-id` is documented as omittable, and a null goal is a real
                # choice rather than a missing field: the store's `task.create` shape
                # requires the key, so the CLI has to send the explicit null.
                payload = {"id": args.id, "title": args.title, "goal_id": args.goal_id}
                extensions = _json_argument(args.extensions, "extensions")
                if extensions is not None:
                    payload["extensions"] = extensions
                result = apply_cli_action(root, "task.create", payload)
            elif args.task_action == "reopen":
                payload = {
                    "task_id": args.task_id, "new_task_id": args.new_task_id,
                    "reason": args.reason,
                }
                if args.title is not None:
                    payload["title"] = args.title
                result = apply_cli_action(root, "task.reopen", payload)
            elif args.task_action == "begin":
                result = apply_cli_action(root, "task.begin", {
                    "task_id": args.task_id, "run_id": args.run_id,
                    "next_action": args.next_action,
                    "owner": args.owner, "session_id": args.session_id,
                    "write_scope": args.write_scope,
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
            result = task_context(open_store(root, heal=True), args.task_id, args.budget_bytes)
        elif args.command == "memory":
            from project_memory import read_memory, sync_memory

            if args.memory_action == "read":
                result = read_memory(root)
            else:
                result = sync_memory(root, _json_argument(args.file, "memory payload"))
        elif args.command == "ledger":
            from state_ledger import export_ledger, verify_ledger

            if args.ledger_action == "export":
                # Never write the ledger straight from the store: if the ledger is
                # ahead (a crash between its fsync and the SQLite commit) a blind
                # export would truncate the durable tail. Reconcile first, which
                # replays that tail or fails closed on divergence, then export.
                store = open_store(root)
                store.reconcile_with_ledger()
                result = export_ledger(store)
            elif args.ledger_action == "list":
                from state_ledger import ledger_path, read_ledger

                if not 1 <= args.limit <= 100:
                    raise ValueError("limit must be between 1 and 100")
                rows = read_ledger(ledger_path(root))
                result = {
                    "count": len(rows),
                    "entries": [
                        {
                            "created_at": row.get("created_at"),
                            "action": row.get("action"),
                            "local_sequence": row.get("local_sequence"),
                        }
                        for row in rows[-args.limit:]
                    ],
                }
            else:
                result = verify_ledger(root)
        elif args.command == "portability-status":
            from state_ledger import portability_status

            result = portability_status(root)
        elif args.command == "render":
            result = refresh_views(root)
        elif args.command == "record":
            if args.record_action in ("show", "list", "links"):
                store = open_store(root, heal=True)
                if args.record_action == "show":
                    # `--kind` is optional: record ids are unique in practice, so a
                    # caller holding only an id should not have to look the kind up.
                    result = (
                        store.get_record(args.kind, args.id)
                        if args.kind
                        else store.find_record(args.id)
                    )
                elif args.record_action == "links":
                    result = store.list_record_links(args.kind, args.id)
                else:
                    if not 1 <= args.limit <= 100:
                        raise ValueError("limit must be between 1 and 100")
                    rows = store.list_records(args.kind)[:args.limit]
                    # The payload is the bulk of a record and rarely what a caller
                    # listing records is after, so it stays behind an explicit flag.
                    result = rows if args.full else [
                        {key: value for key, value in row.items() if key != "payload"}
                        for row in rows
                    ]
            elif args.record_action == "create":
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
            if args.goal_action == "create":
                payload = {"id": args.id, "title": args.title}
                extensions = _json_argument(args.extensions, "extensions")
                if extensions is not None:
                    payload["extensions"] = extensions
                result = apply_cli_action(root, "goal.create", payload)
            elif args.goal_action == "update":
                payload = {"id": args.id}
                conditions = _json_argument(args.success_conditions, "success_conditions")
                if conditions is not None:
                    payload["success_conditions"] = conditions
                required = _json_argument(args.required_evidence, "required_evidence")
                if required is not None:
                    payload["required_evidence"] = required
                # Attribution is what the high-risk completion gate needs to establish
                # reviewer independence, so it has to be reachable without hand-editing
                # the ledger (DEC-070).
                if args.implementer is not None:
                    payload["implementer"] = args.implementer
                if args.owner is not None:
                    payload["owner"] = args.owner
                result = apply_cli_action(root, "goal.update", payload)
            elif args.goal_action == "cancel":
                result = apply_cli_action(root, "goal.cancel", {
                    "id": args.id, "reason": args.reason,
                    "child_policy": args.child_policy,
                })
            else:
                result = apply_cli_action(root, "goal.complete", {"id": args.id})
        elif args.command == "workspace":
            store = open_store(root, heal=True)
            if args.workspace_action == "clear":
                if args.dry_run:
                    result = store.workspace_plan()
                else:
                    if args.plan_digest is None or args.expected_revision is None:
                        raise StateError(
                            "invalid_input",
                            "workspace clear needs --expected-revision and --plan-digest; "
                            "run it with --dry-run first",
                        )
                    current = store.status()["revision"]
                    if current != args.expected_revision:
                        raise StateError(
                            "state_conflict",
                            f"Workspace moved to revision {current}; "
                            f"expected {args.expected_revision}. Re-run --dry-run.",
                        )
                    result = apply_cli_action(root, "workspace.clear", {
                        "reason": args.reason, "plan_digest": args.plan_digest,
                        "scope": args.scope,
                    })
            elif args.workspace_action == "status":
                plan = store.workspace_plan()
                result = {
                    "generation": plan["generation"], "revision": plan["revision"],
                    "affected_goal_ids": plan["affected_goal_ids"],
                    "affected_task_ids": plan["affected_task_ids"],
                    "active_run_ids": plan["active_run_ids"],
                    "warnings": plan["warnings"],
                }
            else:
                result = store.workspace_history()
        elif args.command == "verification":
            # The reviewer's verification entry point. It resolves the action through the
            # trusted registry instead of being handed a command string, so the permission
            # it needs is one narrow allow rather than a general shell grant.
            import verification_runner

            if args.verification_action == "preflight":
                result = verification_runner.preflight(args.action, root, args.path)
            else:
                result = verification_runner.run(
                    args.action, root, args.path, timeout=args.timeout)
        elif args.command == "gate":
            result = open_store(root, heal=True).gate_task(args.task)
        elif args.command == "review":
            result = apply_cli_action(root, "review.record", {
                "id": args.id, "task_id": args.task_id, "reviewer": args.reviewer,
                "verdict": args.verdict, "scope": _json_argument(args.scope, "scope"),
                "evidence_refs": args.evidence_ref,
            })
        elif args.command == "status":
            if not is_transactional(root):
                raise StateError(
                    "not_a_project",
                    f"No Project Log format 2 found under {root}: expected "
                    f"{root / '.project-log' / 'state-format.json'}. "
                    "Run 'vibe init' to create one.",
                )
            result = open_store(root, heal=True).status()
        elif args.command == "validate":
            if not is_transactional(root):
                raise StateError(
                    "not_a_project",
                    f"No Project Log format 2 found under {root}: expected "
                    f"{root / '.project-log' / 'state-format.json'}. "
                    "Run 'vibe init' to create one.",
                )
            errors = open_store(root).validate()
            print(json.dumps({"errors": errors}, ensure_ascii=True))
            return int(bool(errors))
        if result is not None:
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0
    except (StateError, OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": getattr(exc, "code", "invalid_input"), "message": str(exc)}}, ensure_ascii=True), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
