"""Legacy Project Log migration preview and lossless rollback bundles.

The preview never guesses business facts: it reads the legacy files, reports
what cannot be mapped, and never consults file modification times. Nothing is
rewritten in place, so a rollback cannot silently drop either the legacy
records or the records written after a migration.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import uuid

import yaml

from state_evidence import from_legacy
from state_store import StateError


LEGACY_SOURCES = {
    "tasks": ".project-log/tasks/task-list.yaml",
    "decisions": ".project-log/decisions/decision-log.yaml",
    "questions": ".project-log/business-logic/open-questions.yaml",
    "evidence": ".project-log/loop/evidence-index.yaml",
    "goal": ".project-log/goals/active-goal.yaml",
    "run": ".project-log/loop/active-run.yaml",
}
TASK_KNOWN_FIELDS = {
    "id", "title", "kind", "phase", "goal", "status", "authority", "risk", "tags",
    "related_business_logic", "related_decisions", "depends_on", "blocked_by_questions",
    "spec_ref", "inputs", "outputs", "plan", "done_when", "verification", "result",
}
TASK_STATUSES = {
    "pending", "ready", "in-progress", "blocked", "handed-off",
    "implemented-unverified", "cancelled", "done",
}
MAX_ENTRIES = 20000


def _load(path: Path, key: str) -> list[dict]:
    if not path.is_file():
        return []
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeError) as error:
        raise StateError("unreadable_legacy", f"Cannot parse {path}: {error}") from error
    if document is None:
        return []
    if type(document) is not dict:
        raise StateError("unreadable_legacy", f"{path} must contain a mapping")
    entries = document.get(key, [])
    if type(entries) is not list or len(entries) > MAX_ENTRIES:
        raise StateError("unreadable_legacy", f"{path}:{key} must be a bounded list")
    return [entry for entry in entries if type(entry) is dict]


def _load_mapping(path: Path):
    """Read one legacy YAML mapping, or None when the file is absent or empty."""
    if not path.is_file():
        return None
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeError) as error:
        raise StateError("unreadable_legacy", f"Cannot parse {path}: {error}") from error
    if document is None:
        return None
    if type(document) is not dict:
        raise StateError("unreadable_legacy", f"{path} must contain a mapping")
    return document


def _reference_list(entry: dict, key: str, identifier, conflicts: list) -> list:
    """Return a validated id list; a malformed value is reported, never iterated."""
    value = entry.get(key)
    if value is None:
        return []
    if type(value) is not list or any(type(item) is not str or not item.strip() for item in value):
        conflicts.append({"kind": "malformed_task_field", "section": "tasks",
                          "detail": f"{identifier}: {key} must be a list of ids"})
        return []
    return value


def _load_active_goal(path: Path):
    """The legacy task list's own active-goal pointer, or None when absent."""
    document = _load_mapping(path)
    if document is None:
        return None
    value = document.get("active_goal")
    return value if type(value) is str and value.strip() else None


def _tree_digest(path: Path) -> str | None:
    """Hash relative paths and bytes of a legacy tree, ignoring migration scratch space."""
    if not path.exists():
        return None
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix()
        if relative == ".migration" or relative.startswith(".migration/"):
            continue
        if item.is_symlink():
            digest.update(b"L\0" + relative.encode("utf-8") + b"\0" + os.readlink(item).encode("utf-8"))
        elif item.is_file():
            digest.update(b"F\0" + relative.encode("utf-8") + b"\0")
            digest.update(item.read_bytes())
        elif item.is_dir():
            digest.update(b"D\0" + relative.encode("utf-8") + b"\0")
    return digest.hexdigest()


def preview(root) -> dict:
    """Dry-run report of what a migration would keep, conflict on or drop."""
    base = Path(root)
    if not base.is_dir():
        raise StateError("missing_root", f"Legacy project root does not exist: {base}")
    inventory: dict[str, int] = {}
    present: dict[str, bool] = {}
    for name, relative in LEGACY_SOURCES.items():
        present[name] = (base / relative).is_file()
    tasks = _load(base / LEGACY_SOURCES["tasks"], "tasks")
    decisions = _load(base / LEGACY_SOURCES["decisions"], "decisions")
    questions = _load(base / LEGACY_SOURCES["questions"], "questions")
    evidence = _load(base / LEGACY_SOURCES["evidence"], "evidence")
    inventory.update({"tasks": len(tasks), "decisions": len(decisions),
                      "questions": len(questions), "evidence": len(evidence)})

    conflicts: list[dict] = []
    missing: list[dict] = []
    unsupported: list[dict] = []
    seen: dict[str, set] = {"tasks": set(), "decisions": set(), "questions": set(), "evidence": set()}
    for name, entries in (("tasks", tasks), ("decisions", decisions),
                          ("questions", questions), ("evidence", evidence)):
        for entry in entries:
            identifier = entry.get("id")
            if type(identifier) is not str or not identifier.strip():
                conflicts.append({"kind": "missing_id", "section": name, "detail": repr(identifier)})
                continue
            if identifier in seen[name]:
                conflicts.append({"kind": "duplicate_id", "section": name, "detail": identifier})
                continue
            seen[name].add(identifier)

    task_ids = seen["tasks"]
    decision_ids = seen["decisions"]
    question_ids = seen["questions"]
    for entry in tasks:
        identifier = entry.get("id")
        status = entry.get("status")
        if status not in TASK_STATUSES:
            unsupported.append({"kind": "unsupported_task_status", "section": "tasks",
                                "detail": f"{identifier}: {status!r}"})
        for dependency in _reference_list(entry, "depends_on", identifier, conflicts):
            if dependency not in task_ids:
                missing.append({"kind": "unknown_task_dependency", "section": "tasks",
                                "detail": f"{identifier} -> {dependency}"})
        for question in _reference_list(entry, "blocked_by_questions", identifier, conflicts):
            if question not in question_ids:
                missing.append({"kind": "unknown_question", "section": "tasks",
                                "detail": f"{identifier} -> {question}"})
        for decision in _reference_list(entry, "related_decisions", identifier, conflicts):
            if decision not in decision_ids:
                missing.append({"kind": "unknown_decision", "section": "tasks",
                                "detail": f"{identifier} -> {decision}"})
        unknown = sorted(set(entry) - TASK_KNOWN_FIELDS)
        if unknown:
            unsupported.append({"kind": "unknown_task_field", "section": "tasks",
                                "detail": f"{identifier}: {', '.join(unknown)}"})

    converted_evidence = []
    for entry in evidence:
        try:
            converted_evidence.append(from_legacy(entry, base))
        except StateError as error:
            unsupported.append({"kind": "unconvertible_evidence", "section": "evidence",
                                "detail": f"{entry.get('id')!r}: {error}"})
    historical = [item for item in converted_evidence if item["result"] == "passed"]
    unknown_result = [item for item in converted_evidence if item["result"] == "unknown"]

    run = {}
    run_path = base / LEGACY_SOURCES["run"]
    if run_path.is_file():
        try:
            run = yaml.safe_load(run_path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError, UnicodeError) as error:
            conflicts.append({"kind": "unreadable_active_run", "section": "run", "detail": str(error)})
        if type(run) is not dict:
            conflicts.append({"kind": "unreadable_active_run", "section": "run", "detail": "not a mapping"})
            run = {}
    run_task = run.get("task_id")
    if run_task and run_task not in task_ids:
        missing.append({"kind": "unknown_run_task", "section": "run", "detail": str(run_task)})

    report = {
        "root": str(base),
        "present": present,
        "inventory": inventory,
        "conflicts": conflicts,
        "missing": missing,
        "unsupported": unsupported,
        "unmappable_history": {
            "reason": "legacy records have no command envelope, so no receipt is invented for them",
            "tasks": len(tasks),
            "decisions": len(decisions),
            "evidence": len(evidence),
            "evidence_with_historical_pass": len(historical),
            "evidence_with_unknown_result": len(unknown_result),
        },
        "ready": not conflicts and not missing,
        "note": "no modification-time inference and no in-place rewrite is performed",
    }
    report["source_digest"] = _tree_digest(base / ".project-log")
    report["preview_hash"] = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return report


def rollback_bundle(store, root, destination) -> dict:
    """Write a legacy-shaped snapshot that keeps old fields and new records."""
    base = Path(root)
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise StateError("destination_exists", f"Refusing to overwrite {target}")
    target.mkdir(parents=True)
    legacy_tasks = _load(base / LEGACY_SOURCES["tasks"], "tasks")
    legacy_evidence = _load(base / LEGACY_SOURCES["evidence"], "evidence")
    legacy_decisions = _load(base / LEGACY_SOURCES["decisions"], "decisions")
    legacy_questions = _load(base / LEGACY_SOURCES["questions"], "questions")
    legacy_goal = _load_mapping(base / LEGACY_SOURCES["goal"])
    legacy_active_goal = _load_active_goal(base / LEGACY_SOURCES["tasks"])
    bundle = store.export_bundle()
    new_tasks = [
        {"id": row["id"], "title": row["title"], "status": row["status"], "goal": row["goal_id"],
         "run_id": row["run_id"], "next_action": row["next_action"], "summary": row["summary"],
         "extensions": json.loads(row["extensions"]), "source": "vibe-state"}
        for row in bundle["tasks"]
    ]
    new_evidence = [
        {"id": row["command_id"], "kind": "command-receipt", "subject": row["action"],
         "result": "recorded", "origin_kind": row["origin_kind"],
         "origin_context_id": row["origin_context_id"], "origin_revision": row["origin_revision"],
         "receipt": json.loads(row["receipt_json"]), "source": "vibe-state"}
        for row in bundle["ledger"]
    ]
    (target / "tasks").mkdir()
    (target / "loop").mkdir()
    (target / "decisions").mkdir()
    (target / "business-logic").mkdir()
    (target / "goals").mkdir()
    (target / "tasks/task-list.yaml").write_text(
        yaml.safe_dump({"version": "rollback", "active_goal": legacy_active_goal,
                        "preserved_legacy_tasks": legacy_tasks, "tasks": new_tasks},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")
    (target / "loop/evidence-index.yaml").write_text(
        yaml.safe_dump({"schema_version": 1,
                        "preserved_legacy_evidence": legacy_evidence,
                        "evidence": new_evidence},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")
    (target / "decisions/decision-log.yaml").write_text(
        yaml.safe_dump({"version": "rollback", "preserved_legacy_decisions": legacy_decisions},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")
    (target / "business-logic/open-questions.yaml").write_text(
        yaml.safe_dump({"version": "rollback", "preserved_legacy_questions": legacy_questions},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")
    (target / "goals/active-goal.yaml").write_text(
        yaml.safe_dump({"version": "rollback", "preserved_legacy_goal": legacy_goal},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")
    (target / "ROLLBACK.json").write_text(
        json.dumps({
            "project_id": bundle["project_id"], "context_id": bundle["context_id"],
            "local_revision": bundle["local_revision"], "base_snapshot": bundle["base_snapshot"],
            "preserved_legacy_tasks": len(legacy_tasks),
            "preserved_legacy_evidence": len(legacy_evidence),
            "preserved_legacy_decisions": len(legacy_decisions),
            "preserved_legacy_questions": len(legacy_questions),
            "preserved_legacy_goal": legacy_goal.get("id") if legacy_goal else None,
            "preserved_legacy_active_goal": legacy_active_goal,
            "new_tasks": len(new_tasks), "new_evidence": len(new_evidence),
            "source_state_untouched": os.fspath(store.path),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "destination": str(target),
        "preserved_legacy_tasks": len(legacy_tasks),
        "preserved_legacy_evidence": len(legacy_evidence),
        "preserved_legacy_decisions": len(legacy_decisions),
        "preserved_legacy_questions": len(legacy_questions),
        "preserved_legacy_goal": legacy_goal.get("id") if legacy_goal else None,
        "preserved_legacy_active_goal": legacy_active_goal,
        "new_tasks": len(new_tasks),
        "new_evidence": len(new_evidence),
        "note": "the new-format state was read only; restoring this bundle cannot discard post-migration records",
    }


MIGRATION_DIR = ".migration"
JOURNAL_NAME = "journal.json"


def _apply(store, action: str, payload: dict) -> dict:
    return store.apply({
        "schema_version": 1,
        "command_id": uuid.uuid4().hex,
        "expected_revision": store.status()["revision"],
        "action": action,
        "payload": payload,
    })


def _write_unmapped(directory: Path, entries: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "unmapped.json").write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / "README.md").write_text(
        "# Unmapped legacy history\n\n"
        "These entries could not be represented losslessly in the format 2 state machine. "
        "They are retained here as evidence; migration does not delete or silently rewrite them.\n",
        encoding="utf-8",
    )


def _task_status(status: str) -> str:
    return {
        "pending": "ready",
        "ready": "ready",
        "in-progress": "in-progress",
        "blocked": "blocked",
        "handed-off": "handed-off",
        "implemented-unverified": "implemented-unverified",
        "cancelled": "cancelled",
        "done": "implemented-unverified",
    }.get(status, "ready")


def _populate_staging(store, root: Path, unmapped: list[dict]) -> None:
    """Build a format 2 store from legacy facts without inventing business state."""
    goal_document = _load_mapping(root / LEGACY_SOURCES["goal"]) or {}
    goal = goal_document.get("goal") if type(goal_document) is dict else None
    goal_id = None
    if type(goal) is dict:
        goal_id = str(goal.get("id") or "GOAL-MIGRATED")
        extensions = dict(goal)
        extensions.setdefault("legacy_migrated", True)
        _apply(store, "goal.create", {
            "id": goal_id,
            "title": str(goal.get("statement") or goal.get("title") or goal_id),
            "extensions": extensions,
        })

    tasks = _load(root / LEGACY_SOURCES["tasks"], "tasks")
    task_statuses: dict[str, str] = {}
    for task in tasks:
        task_id = task.get("id")
        if type(task_id) is not str or not task_id.strip():
            unmapped.append({"section": "tasks", "reason": "missing id", "entry": task})
            continue
        legacy_status = task.get("status")
        extensions = dict(task)
        extensions["legacy_status"] = legacy_status
        extensions["legacy_migrated"] = True
        try:
            _apply(store, "task.create", {
                "id": task_id,
                "title": str(task.get("title") or task_id),
                "goal_id": goal_id,
                "extensions": extensions,
            })
        except StateError as error:
            unmapped.append({
                "section": "tasks", "id": task_id,
                "reason": f"task.create failed: {error}", "entry": task,
            })
            continue
        task_statuses[task_id] = str(legacy_status)

    evidence_entries = _load(root / LEGACY_SOURCES["evidence"], "evidence")
    for entry in evidence_entries:
        evidence_id = entry.get("id")
        status = entry.get("status")
        if status not in {"candidate", "valid", "failed", "stale", "superseded", "invalid"}:
            unmapped.append({
                "section": "evidence", "id": evidence_id,
                "reason": f"unsupported evidence status {status!r}", "entry": entry,
            })
            continue
        covers = entry.get("covers") if type(entry.get("covers")) is dict else {}
        task_ids = covers.get("tasks") if type(covers.get("tasks")) is list else []
        task_id = task_ids[0] if len(task_ids) == 1 and task_ids[0] in task_statuses else None
        try:
            _apply(store, "evidence.record", {
                "id": str(evidence_id),
                "kind": str(entry.get("kind") or "legacy"),
                "subject": str(entry.get("subject") or evidence_id),
                "status": status,
                "task_id": task_id,
                "covers": {
                    "files": covers.get("files", []),
                    "requirements": covers.get("requirements", []),
                    "tasks": covers.get("tasks", []),
                },
                "version_binding": entry.get("version_binding") or {},
            })
        except StateError as error:
            unmapped.append({
                "section": "evidence", "id": evidence_id,
                "reason": f"evidence.record failed: {error}", "entry": entry,
            })

    decisions = _load(root / LEGACY_SOURCES["decisions"], "decisions")
    for decision in decisions:
        identifier = decision.get("id")
        if type(identifier) is not str or not identifier.strip():
            unmapped.append({"section": "decisions", "reason": "missing id", "entry": decision})
            continue
        status = decision.get("status")
        if status not in {"proposed", "active", "experimental", "rejected", "superseded", "archived"}:
            status = "archived"
        try:
            _apply(store, "record.create", {
                "kind": "decision", "id": identifier,
                "title": str(decision.get("statement") or decision.get("title") or identifier),
                "status": status, "payload": decision,
            })
        except StateError as error:
            unmapped.append({
                "section": "decisions", "id": identifier,
                "reason": f"record.create failed: {error}", "entry": decision,
            })

    questions = _load(root / LEGACY_SOURCES["questions"], "questions")
    for question in questions:
        identifier = question.get("id")
        if type(identifier) is not str or not identifier.strip():
            unmapped.append({"section": "questions", "reason": "missing id", "entry": question})
            continue
        status = question.get("status")
        if status not in {"open", "resolved", "accepted", "archived"}:
            status = "archived"
        try:
            _apply(store, "record.create", {
                "kind": "alignment", "id": identifier,
                "title": str(question.get("question") or question.get("title") or identifier),
                "status": status, "payload": question,
            })
        except StateError as error:
            unmapped.append({
                "section": "questions", "id": identifier,
                "reason": f"record.create failed: {error}", "entry": question,
            })

    run_document = _load_mapping(root / LEGACY_SOURCES["run"]) or {}
    legacy_run_task = run_document.get("task_id") if type(run_document) is dict else None
    for task in tasks:
        task_id = task.get("id")
        legacy_status = task.get("status")
        if task_id not in task_statuses or legacy_status in {None, "pending", "ready"}:
            continue
        run_id = legacy_run_task if legacy_run_task == task_id else f"RUN-MIG-{uuid.uuid4().hex[:8]}"
        try:
            if legacy_status == "cancelled":
                _apply(store, "task.cancel", {
                    "task_id": task_id,
                    "reason": str(task.get("cancel_reason") or "legacy cancelled task"),
                })
                continue
            if legacy_status in {"done", "implemented-unverified"}:
                gate = store.gate_task(task_id)
                if gate["decision"] != "allowed":
                    unmapped.append({
                        "section": "tasks", "id": task_id,
                        "reason": "completion gate could not be reproduced: "
                                  + "; ".join(gate["blocking"]),
                        "entry": task,
                    })
                    continue
            _apply(store, "task.begin", {
                "task_id": task_id, "run_id": run_id,
                "next_action": str(task.get("next_action") or "continue migrated task"),
            })
            if legacy_status == "blocked":
                _apply(store, "task.wait", {
                    "task_id": task_id, "kind": "dependency",
                    "reason": str(task.get("blocked_reason") or "legacy blocked task"),
                    "resume_when": str(task.get("resume_when") or "blocker resolved"),
                })
            elif legacy_status == "handed-off":
                _apply(store, "task.handoff", {
                    "task_id": task_id,
                    "next_action": str(task.get("next_action") or "continue migrated task"),
                })
            elif legacy_status in {"done", "implemented-unverified"}:
                _apply(store, "task.finish", {
                    "task_id": task_id,
                    "summary": str(task.get("result", {}).get("summary")
                                   if type(task.get("result")) is dict else "legacy completed work"),
                })
        except StateError as error:
            unmapped.append({
                "section": "tasks", "id": task_id,
                "reason": f"lifecycle replay failed: {error}", "entry": task,
            })


def _migration_paths(root: Path, preview_hash: str) -> tuple[Path, Path, Path]:
    log = root / ".project-log"
    migration = log / MIGRATION_DIR
    return (
        migration / f"backup-{preview_hash[:12]}",
        migration / f"staging-{preview_hash[:12]}",
        migration / JOURNAL_NAME,
    )


def _write_journal(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# The layout ``vibe init`` produces for a format 2 project. Migration has to
# produce the same tree, otherwise a migrated project is missing the local-state
# guard and the exchange attributes that init would have written.
FORMAT_TWO_LAYOUT_FILES = (
    # Local operational state: the state store, the migration journal/backups and
    # the rollback recovery bundle all live outside the committed layout.
    (Path(".gitignore"), ".state/\n.migration/\nlegacy/new-writes/\n"),
    (Path("exchange/.gitattributes"), "* -text\n"),
)
SKIP_ENTRIES = {MIGRATION_DIR, "legacy", "state-format.json", ".state"}
# Long-form documentation is not part of the legacy *format*: section 4 of the
# contract keeps it at ``.project-log/docs/**`` in both formats, so migration must
# not relocate it (a doc_ref recorded during migration would otherwise break).
PRESERVED_ENTRIES = {"docs"}


def _is_format_two_layout_entry(entry: Path) -> bool:
    """True when a top-level entry already matches the format 2 layout."""
    if entry.name == ".gitignore":
        return entry.is_file() and entry.read_text(encoding="utf-8") == ".state/\n"
    if entry.name == "exchange":
        attributes = entry / ".gitattributes"
        return (
            entry.is_dir()
            and attributes.is_file()
            and attributes.read_text(encoding="utf-8") == "* -text\n"
        )
    return False


def _ensure_format_two_layout(log: Path) -> None:
    (log / ".state").mkdir(parents=True, exist_ok=True)
    for relative, content in FORMAT_TWO_LAYOUT_FILES:
        target = log / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(content, encoding="utf-8", newline="\n")


def _switch_to_format_two(root: Path, staging: Path, journal_path: Path, metadata: dict) -> dict:
    """Move a validated staging store into place; the marker is the commit point.

    Every step is idempotent and ordered so that an interrupted switch is always
    resumable: the database is placed first, legacy entries are moved second, and
    the format marker is written last. A crash before the marker leaves a legacy
    project (or a partially switched one that ``resume`` can finish), never a
    project that claims format 2 without a store.
    """
    from state_context import git_context

    log = root / ".project-log"
    legacy = log / "legacy"
    legacy.mkdir(parents=True, exist_ok=True)
    context_id, directory = git_context(root)
    final_directory = directory / metadata["project_id"] / context_id
    final_database = final_directory / "state.sqlite3"
    if not final_database.is_file():
        staged = staging / "state.sqlite3"
        if not staged.is_file():
            raise StateError(
                "migration_validation_failed",
                f"State database does not exist in staging: {staged}",
            )
        final_directory.mkdir(parents=True, exist_ok=True)
        os.replace(staged, final_database)
    for entry in list(log.iterdir()):
        if (
            entry.name in SKIP_ENTRIES
            or entry.name in PRESERVED_ENTRIES
            or _is_format_two_layout_entry(entry)
        ):
            continue
        target = legacy / entry.name
        if target.exists() or target.is_symlink():
            raise StateError("migration_conflict", f"Legacy backup target already exists: {target}")
        os.replace(entry, target)
    _ensure_format_two_layout(log)
    marker = {"format": 2, "project_id": metadata["project_id"]}
    marker_path = log / "state-format.json"
    if not marker_path.is_file():
        marker_path.write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
    _write_journal(journal_path, {**metadata, "status": "switched"})
    return {"state_path": str(final_database), "marker": marker}


def _final_state_path(root: Path, project_id: str) -> Path:
    """Where the format 2 store for ``project_id`` belongs in this worktree."""
    from state_context import git_context

    context_id, directory = git_context(root)
    return directory / project_id / context_id / "state.sqlite3"


def apply(root, confirm: str) -> dict:
    """Explicitly migrate a legacy Project Log after a matching preview confirmation."""
    base = Path(root)
    report = preview(base)
    if (base / ".project-log/state-format.json").exists():
        raise StateError("already_format_two", "Project already has a format 2 marker")
    if confirm != report["preview_hash"]:
        raise StateError(
            "confirmation_required",
            f"Migration requires --confirm {report['preview_hash']} (source may have changed)",
        )
    if not report["ready"]:
        raise StateError("migration_conflict", "Migration preview is not ready")
    if _tree_digest(base / ".project-log") != report["source_digest"]:
        raise StateError("source_changed", "Legacy Project Log changed after preview")
    backup, staging, journal_path = _migration_paths(base, report["preview_hash"])
    migration = base / ".project-log" / MIGRATION_DIR
    migration.mkdir(parents=True, exist_ok=True)
    # The backup path is keyed by the preview hash, so an existing backup was taken
    # from this exact source state. Reuse it: a crash during generation must not
    # block the retry that the migration window explicitly allows.
    if not backup.exists():
        shutil.copytree(base / ".project-log", backup, ignore=shutil.ignore_patterns(MIGRATION_DIR))
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    from state_context import git_context
    from state_store import Store

    project_id = uuid.uuid4().hex
    context_id, _directory = git_context(base)
    store = Store(staging / "state.sqlite3", project_id, context_id, base)
    store.initialize()
    unmapped: list[dict] = list(report.get("unsupported", []))
    _populate_staging(store, base, unmapped)
    errors = store.validate()
    if errors:
        raise StateError("migration_validation_failed", "; ".join(errors))
    _write_unmapped(base / ".project-log/legacy/unmapped", unmapped)
    metadata = {
        "schema_version": 1,
        "preview_hash": report["preview_hash"],
        "source_digest": report["source_digest"],
        "project_id": project_id,
        "context_id": context_id,
        "backup": str(backup),
        "staging": str(staging),
        "status": "generated",
        "inventory": report["inventory"],
        "unmapped": len(unmapped),
    }
    _write_journal(journal_path, metadata)
    try:
        switched = _switch_to_format_two(base, staging, journal_path, metadata)
    except Exception as error:
        _write_journal(journal_path, {**metadata, "status": "failed", "error": str(error)})
        raise
    return {
        "status": "switched",
        "preview_hash": report["preview_hash"],
        "project_id": project_id,
        "unmapped": len(unmapped),
        "backup": str(backup),
        **switched,
    }


def resume(root) -> dict:
    """Resume a migration journal; an already-switched project is validated read-only."""
    base = Path(root)
    journal_path = base / ".project-log" / MIGRATION_DIR / JOURNAL_NAME
    if not journal_path.is_file():
        raise StateError("migration_not_found", "No migration journal exists")
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StateError("migration_journal_invalid", str(error)) from error
    if (base / ".project-log/state-format.json").exists():
        from state_context import open_store

        store = open_store(base)
        staging = Path(journal.get("staging", ""))
        if not store.path.is_file():
            # A marker without a store is an interrupted switch: finish the remaining
            # steps from staging instead of leaving the project split.
            if staging.is_dir() and (staging / "state.sqlite3").is_file():
                return {
                    "status": "switched",
                    **_switch_to_format_two(base, staging, journal_path, journal),
                }
            raise StateError(
                "migration_validation_failed",
                f"Format marker exists but the state store is missing: {store.path}",
            )
        errors = store.validate()
        if errors:
            raise StateError("migration_validation_failed", "; ".join(errors))
        return {"status": "switched", "journal": journal}
    staging = Path(journal.get("staging", ""))
    project_id = journal.get("project_id")
    if project_id:
        # The journal records a generated store, so this is a switch that was
        # interrupted between its first and last step. The source tree has already
        # changed (database placed, legacy entries moved), so re-running `apply`
        # would fail its own source-digest check; finish the switch instead.
        final = _final_state_path(base, project_id)
        if (staging / "state.sqlite3").is_file() or final.is_file():
            return {
                "status": "switched",
                **_switch_to_format_two(base, staging, journal_path, journal),
            }
        raise StateError(
            "migration_validation_failed",
            "Migration journal records a generated store, but neither the staged nor the "
            f"final state database exists (staging={staging}, final={final})",
        )
    return apply(base, str(journal.get("preview_hash")))


def rollback(root, destination=None) -> dict:
    """Restore legacy files and preserve format 2 writes under legacy/new-writes."""
    base = Path(root)
    marker = base / ".project-log/state-format.json"
    legacy = base / ".project-log/legacy"
    if not marker.is_file():
        raise StateError("not_migrated", "Project is not in format 2")
    if destination is None:
        destination = legacy / "new-writes"
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise StateError("destination_exists", f"Refusing to overwrite {target}")
    from state_context import open_store

    store = open_store(base)
    bundle = store.export_bundle()
    target.mkdir(parents=True)
    (target / "bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    marker.unlink()
    legacy_names = {entry.name for entry in legacy.iterdir()}
    for entry in list(legacy.iterdir()):
        if entry.name in {"new-writes", "unmapped"}:
            continue
        os.replace(entry, base / ".project-log" / entry.name)
    # Remove the format 2 layout that migration itself created; anything the
    # legacy project already owned was restored above and must stay untouched.
    for relative, content in FORMAT_TWO_LAYOUT_FILES:
        if relative.parts[0] in legacy_names:
            continue
        path = base / ".project-log" / relative
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            path.unlink()
    exchange_directory = base / ".project-log/exchange"
    if exchange_directory.is_dir() and not any(exchange_directory.iterdir()):
        exchange_directory.rmdir()
    state_directory = base / ".project-log/.state"
    if state_directory.exists():
        shutil.move(str(state_directory), str(target / "state"))
    return {
        "status": "rolled-back",
        "restored": [entry.name for entry in legacy.iterdir()
                     if entry.name not in {"new-writes", "unmapped"}],
        "preserved_new_writes": str(target),
    }
