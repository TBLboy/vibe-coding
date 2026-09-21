"""Legacy Project Log migration preview and lossless rollback bundles.

The preview never guesses business facts: it reads the legacy files, reports
what cannot be mapped, and never consults file modification times. Nothing is
rewritten in place, so a rollback cannot silently drop either the legacy
records or the records written after a migration.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

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
            conflicts.append({"kind": "unsupported_task_status", "section": "tasks",
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
            conflicts.append({"kind": "unconvertible_evidence", "section": "evidence",
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

    return {
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
