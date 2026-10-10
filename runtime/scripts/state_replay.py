"""Deterministic replay of the command ledger into entity state.

The ledger is the source of truth; the SQLite entity tables are a projection of
it. `reduce_ledger` is therefore a pure function of the recorded commands: it
may not consult the clock, the filesystem, or any other mutable external state.
Whatever a command decided from the outside world (a file hash, a test result,
the current time) was already frozen into its request or receipt when the
command was accepted, and replay reads it back from there.

Gate decisions are not re-evaluated here. A recorded `task.finish` receipt is
proof that the completion gate passed at accept time; replay applies the effect
instead of re-running the check, because the check depends on the working tree
and would not be reproducible years later.

Replay is shared by the live audit (`Store._verify_ledger`) and the migration
tooling so the two can never drift apart.
"""
from __future__ import annotations

import hashlib
import json

from state_store import (
    StateError,
    _evidence_covers,
    _evidence_refs,
    _json,
    _record_payload,
    _version_binding,
)


def _entry_request(entry) -> dict:
    try:
        return json.loads(entry["request_json"])
    except (TypeError, ValueError) as error:
        raise StateError("invalid_ledger", f"Ledger request is not valid JSON: {error}") from error


def _require(collection, key, label: str):
    value = collection.get(key)
    if value is None:
        raise StateError("invalid_ledger", f"Ledger references an unknown {label}: {key}")
    return value


def _resolve_open_blocker(open_blockers: dict, task_id: str, sequence: int) -> None:
    blocker = open_blockers.pop(task_id, None)
    if blocker is not None:
        blocker["resolved_sequence"] = sequence


GOAL_OPEN_STATUSES = ("draft", "active", "waiting-user", "blocked")
TASK_OPEN_STATUSES = ("ready", "in-progress", "waiting-user", "blocked", "handed-off")


def workspace_plan_digest(generation: int, goal_ids, task_ids, run_ids) -> str:
    """Stable digest of a ``workspace.clear`` plan.

    Shared by the live transition and by replay, so the two can never disagree about
    which plan a committed command was allowed to clear. The live side builds the
    lists with SQL, the replay side in memory, but the encoding is one function.
    """
    encoded = json.dumps(
        {
            "generation": generation, "goals": list(goal_ids),
            "tasks": list(task_ids), "runs": list(run_ids),
        },
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _active_workspace(goals: dict, tasks: dict, runs: dict, generation: int) -> dict:
    """The same view ``Store._workspace_plan`` derives from SQL, in created order."""
    ordered_goals = sorted(
        (row for row in goals.values() if row["status"] in GOAL_OPEN_STATUSES),
        key=lambda row: row["created_sequence"],
    )
    ordered_tasks = sorted(
        (row for row in tasks.values() if row["status"] in TASK_OPEN_STATUSES),
        key=lambda row: row["created_sequence"],
    )
    ordered_runs = sorted(
        (row for row in runs.values() if row["status"] == "active"),
        key=lambda row: row["created_sequence"],
    )
    goal_ids = [row["id"] for row in ordered_goals]
    task_ids = [row["id"] for row in ordered_tasks]
    run_ids = [row["id"] for row in ordered_runs]
    return {
        "generation": generation, "affected_goal_ids": goal_ids,
        "affected_task_ids": task_ids, "active_run_ids": run_ids,
        "plan_digest": workspace_plan_digest(generation, goal_ids, task_ids, run_ids),
    }


def reduce_ledger(entries, with_results: bool = False):
    """Rebuild every entity row from ordered ledger entries.

    `entries` is an iterable of mappings carrying the `commands` columns. Rows
    are returned in the same shape and order as ``Store._entity_rows`` so the
    result can be compared with a live store or used to write a fresh one.

    When `with_results` is true the return value is ``(state, results)`` where
    ``results`` maps each entry's `local_sequence` to the receipt ``result`` the
    authoritative transition would have produced. The audit compares those
    against the stored receipts so receipt validation and entity reconstruction
    share one replay implementation.
    """
    goals: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    runs: dict[str, dict] = {}
    blockers: list[dict] = []
    records: dict[tuple[str, str], dict] = {}
    links: list[dict] = []
    evidence: dict[str, dict] = {}
    reviews: dict[str, dict] = {}
    open_blockers: dict[str, dict] = {}
    blocker_id = 0
    results: dict[int, dict] = {}
    clear_count = 0

    for entry in entries:
        request = _entry_request(entry)
        payload = request["payload"]
        action = request["action"]
        sequence = entry["local_sequence"]

        if action == "goal.create":
            goals[payload["id"]] = {
                "id": payload["id"], "title": payload["title"], "status": "active",
                "extensions": _json(payload.get("extensions", {})),
                "created_sequence": sequence, "updated_sequence": sequence,
            }
            result = {"goal_id": payload["id"], "status": "active"}
        elif action == "goal.update":
            goal = _require(goals, payload["id"], "goal")
            extensions = json.loads(goal["extensions"])
            if not isinstance(extensions, dict):
                extensions = {}
            for key in ("success_conditions", "required_evidence"):
                if key in payload:
                    extensions[key] = payload[key]
            goal["extensions"] = _json(extensions)
            goal["updated_sequence"] = sequence
            result = {"goal_id": payload["id"], "updated": True}
        elif action == "goal.complete":
            goal = _require(goals, payload["id"], "goal")
            # A completed goal closes its never-started tasks, exactly as the live
            # transition does: `task.begin` refuses once the goal is not active, so such a
            # task could never reach a terminal state and would linger forever.
            # `implemented-unverified` is left alone -- it records an implementation that
            # really happened. Insertion order is creation order, matching the live
            # transition.
            for task in tasks.values():
                if task["goal_id"] != payload["id"]:
                    continue
                if task["status"] not in TASK_OPEN_STATUSES:
                    continue
                task["status"] = "cancelled"
                task["cancel_reason"] = "open work closed when its goal completed"
                task["updated_sequence"] = sequence
                for run in runs.values():
                    if run["task_id"] == task["id"] and run["status"] != "finished":
                        run["status"] = "cancelled"
                        run["updated_sequence"] = sequence
            goal["status"] = "complete"
            goal["updated_sequence"] = sequence
            # Same receipt shape as before: the reducer's result must match what the live
            # transition returned for *historical* events too, or the ledger stops reducing.
            result = {"goal_id": payload["id"], "status": "complete"}
        elif action == "goal.cancel":
            goal = _require(goals, payload["id"], "goal")
            if goal["status"] in {"complete", "cancelled"}:
                raise StateError(
                    "invalid_ledger", f"Cannot cancel a {goal['status']} goal"
                )
            policy = payload.get("child_policy", "cancel_open")
            cancelled: list[str] = []
            if policy == "cancel_open":
                # Insertion order is creation order, which is the order the live
                # transition uses, so the receipt's id list is reproducible.
                for task in tasks.values():
                    if task["goal_id"] != payload["id"]:
                        continue
                    if task["status"] not in TASK_OPEN_STATUSES:
                        continue
                    task["status"] = "cancelled"
                    task["cancel_reason"] = "open work cancelled with its goal"
                    task["updated_sequence"] = sequence
                    for run in runs.values():
                        if run["task_id"] == task["id"] and run["status"] != "finished":
                            run["status"] = "cancelled"
                            run["updated_sequence"] = sequence
                    cancelled.append(task["id"])
            goal["status"] = "cancelled"
            goal["updated_sequence"] = sequence
            result = {
                "goal_id": payload["id"], "status": "cancelled",
                "cancelled_task_ids": cancelled,
            }
        elif action == "workspace.clear":
            before = _active_workspace(goals, tasks, runs, clear_count)
            if payload.get("plan_digest") != before["plan_digest"]:
                raise StateError("invalid_ledger", "workspace.clear plan digest mismatch")
            if not before["affected_goal_ids"] and not before["affected_task_ids"]:
                result = {
                    "cleared": False, "generation_before": before["generation"],
                    "generation_after": before["generation"],
                    "cancelled_goal_ids": [], "cancelled_task_ids": [],
                }
            else:
                cancelled_tasks: list[str] = []
                affected = set(before["affected_goal_ids"])
                for task in tasks.values():
                    if task["goal_id"] not in affected:
                        continue
                    if task["status"] not in TASK_OPEN_STATUSES:
                        continue
                    task["status"] = "cancelled"
                    task["cancel_reason"] = "open work cancelled with its goal"
                    task["updated_sequence"] = sequence
                    for run in runs.values():
                        if run["task_id"] == task["id"] and run["status"] != "finished":
                            run["status"] = "cancelled"
                            run["updated_sequence"] = sequence
                    cancelled_tasks.append(task["id"])
                for goal_id in before["affected_goal_ids"]:
                    goals[goal_id]["status"] = "cancelled"
                    goals[goal_id]["updated_sequence"] = sequence
                clear_count += 1
                result = {
                    "cleared": True,
                    "generation_before": before["generation"],
                    "generation_after": before["generation"] + 1,
                    "cancelled_goal_ids": before["affected_goal_ids"],
                    "cancelled_task_ids": cancelled_tasks,
                }
        elif action == "task.create":
            tasks[payload["id"]] = {
                "id": payload["id"], "title": payload["title"], "goal_id": payload["goal_id"],
                "status": "ready", "run_id": None, "next_action": None,
                "summary": None, "cancel_reason": None,
                "extensions": _json(payload.get("extensions", {})),
                "created_sequence": sequence, "updated_sequence": sequence,
            }
            result = {"task_id": payload["id"], "run_id": None, "status": "ready"}
        elif action == "task.reopen":
            old = _require(tasks, payload["task_id"], "task")
            extensions = dict(payload.get("extensions", {}))
            extensions["reopens"] = old["id"]
            extensions["reopen_reason"] = payload["reason"]
            tasks[payload["new_task_id"]] = {
                "id": payload["new_task_id"],
                "title": payload.get("title", old["title"]),
                "goal_id": old["goal_id"], "status": "ready", "run_id": None,
                "next_action": None, "summary": None, "cancel_reason": None,
                "extensions": _json(extensions),
                "created_sequence": sequence, "updated_sequence": sequence,
            }
            result = {
                "task_id": payload["new_task_id"], "run_id": None, "status": "ready",
                "reopens": old["id"],
            }
        elif action == "task.update":
            task = _require(tasks, payload["task_id"], "task")
            extensions = json.loads(task["extensions"])
            if not isinstance(extensions, dict):
                extensions = {}
            for key in ("implementer", "owner"):
                if key in payload:
                    extensions[key] = payload[key].strip()
            task["extensions"] = _json(extensions)
            task["updated_sequence"] = sequence
            result = {"task_id": payload["task_id"], "updated": True}
        elif action in {"task.begin", "task.resume", "task.wait", "task.handoff",
                        "task.finish", "task.cancel"}:
            task = _require(tasks, payload["task_id"], "task")
            run = runs.get(task["run_id"]) if task["run_id"] is not None else None
            if action == "task.begin":
                task["run_id"] = payload["run_id"]
                runs[payload["run_id"]] = {
                    "id": payload["run_id"], "task_id": task["id"], "status": "active",
                    "created_sequence": sequence, "updated_sequence": sequence,
                }
                task["status"] = "in-progress"
                task["next_action"] = payload["next_action"]
            elif action == "task.resume":
                if run is None:
                    raise StateError("invalid_ledger", f"Task {task['id']} resumed without a run")
                run["status"] = "active"
                run["updated_sequence"] = sequence
                task["status"] = "in-progress"
                task["next_action"] = payload["next_action"]
                _resolve_open_blocker(open_blockers, task["id"], sequence)
            elif action == "task.wait":
                status = "waiting-user" if payload["kind"] == "user" else "blocked"
                blocker_id += 1
                blocker = {
                    "id": blocker_id, "task_id": task["id"], "run_id": task["run_id"],
                    "kind": payload["kind"], "reason": payload["reason"],
                    "question_ref": payload.get("question_ref"),
                    "resume_when": payload["resume_when"],
                    "created_sequence": sequence, "resolved_sequence": None,
                }
                blockers.append(blocker)
                open_blockers[task["id"]] = blocker
                if run is not None:
                    run["status"] = status
                    run["updated_sequence"] = sequence
                task["status"] = status
                task["next_action"] = "Wait for: " + payload["resume_when"]
            elif action == "task.handoff":
                if run is not None:
                    run["status"] = "handed-off"
                    run["updated_sequence"] = sequence
                task["status"] = "handed-off"
                task["next_action"] = payload["next_action"]
            elif action == "task.finish":
                if run is not None:
                    run["status"] = "finished"
                    run["updated_sequence"] = sequence
                task["status"] = "implemented-unverified"
                task["summary"] = payload["summary"]
                task["next_action"] = None
            else:
                if run is not None:
                    run["status"] = "cancelled"
                    run["updated_sequence"] = sequence
                task["status"] = "cancelled"
                task["cancel_reason"] = payload["reason"]
                task["next_action"] = None
                _resolve_open_blocker(open_blockers, task["id"], sequence)
            task["updated_sequence"] = sequence
            result = {
                "task_id": task["id"], "run_id": task["run_id"], "status": task["status"],
            }
        elif action == "record.create":
            key = (payload["kind"], payload["id"])
            if key in records:
                raise StateError("invalid_ledger", f"Duplicate record create: {key[0]}/{key[1]}")
            records[key] = {
                "kind": key[0], "id": key[1], "title": payload["title"],
                "status": payload["status"], "revision": 1,
                "payload": _record_payload(payload.get("payload", {})),
                "created_sequence": sequence, "updated_sequence": sequence,
            }
            result = {
                "record_kind": key[0], "record_id": key[1],
                "status": payload["status"], "revision": 1,
            }
        elif action == "record.update":
            key = (payload["kind"], payload["id"])
            record = _require(records, key, "record")
            if record["revision"] != payload["expected_record_revision"]:
                raise StateError(
                    "invalid_ledger",
                    f"Record update revision mismatch for {key[0]}/{key[1]}",
                )
            stored = json.loads(record["payload"])
            if "payload" in payload:
                stored.update(payload["payload"])
            record["payload"] = _record_payload(stored)
            record["status"] = payload.get("status", record["status"])
            record["revision"] += 1
            record["updated_sequence"] = sequence
            result = {
                "record_kind": key[0], "record_id": key[1],
                "status": record["status"], "revision": record["revision"],
            }
        elif action == "record.link":
            link = {
                "from_kind": payload["from_kind"], "from_id": payload["from_id"],
                "relation": payload["relation"], "to_kind": payload["to_kind"],
                "to_id": payload["to_id"], "created_sequence": sequence,
            }
            link_key = (
                link["from_kind"], link["from_id"], link["relation"],
                link["to_kind"], link["to_id"],
            )
            if any(
                (row["from_kind"], row["from_id"], row["relation"],
                 row["to_kind"], row["to_id"]) == link_key
                for row in links
            ):
                raise StateError("invalid_ledger", "Duplicate record link")
            links.append(link)
            result = {
                "from_kind": link["from_kind"], "from_id": link["from_id"],
                "relation": link["relation"], "to_kind": link["to_kind"],
                "to_id": link["to_id"],
            }
        elif action == "evidence.record":
            if payload["id"] in evidence:
                raise StateError("invalid_ledger", f"Duplicate evidence record: {payload['id']}")
            evidence[payload["id"]] = {
                "id": payload["id"], "task_id": payload.get("task_id"),
                "kind": payload["kind"], "subject": payload["subject"],
                "status": payload["status"],
                "covers": _evidence_covers(payload.get("covers")),
                "version_binding": _version_binding(payload.get("version_binding")),
                "recorded_sequence": sequence, "invalidated_sequence": None,
                "invalidation_reason": None,
            }
            result = {"evidence_id": payload["id"], "status": payload["status"]}
        elif action == "evidence.invalidate":
            item = _require(evidence, payload["id"], "evidence")
            if item["invalidated_sequence"] is not None:
                raise StateError(
                    "invalid_ledger", f"Evidence is already invalidated: {payload['id']}",
                )
            item["status"] = "stale"
            item["invalidated_sequence"] = sequence
            item["invalidation_reason"] = payload["reason"]
            result = {
                "evidence_id": payload["id"], "status": "stale", "reason": payload["reason"],
            }
        elif action == "review.record":
            if payload["id"] in reviews:
                raise StateError("invalid_ledger", f"Duplicate review record: {payload['id']}")
            reviews[payload["id"]] = {
                "id": payload["id"], "task_id": payload["task_id"],
                "reviewer": payload["reviewer"], "verdict": payload["verdict"],
                "scope": _json(payload["scope"]),
                "evidence_refs": _evidence_refs(payload["evidence_refs"]),
                "created_sequence": sequence,
            }
            result = {
                "review_id": payload["id"], "task_id": payload["task_id"],
                "verdict": payload["verdict"],
            }
        else:
            raise StateError("invalid_ledger", f"Unknown ledger action: {action}")

        results[sequence] = result

    state = {
        "goals": [goals[key] for key in sorted(goals)],
        "tasks": [tasks[key] for key in sorted(tasks)],
        "runs": [runs[key] for key in sorted(runs)],
        "blockers": sorted(blockers, key=lambda row: row["id"]),
        "records": [records[key] for key in sorted(records)],
        "record_links": sorted(
            links,
            key=lambda row: (row["from_kind"], row["from_id"], row["relation"],
                             row["to_kind"], row["to_id"]),
        ),
        "evidence": [evidence[key] for key in sorted(evidence)],
        "reviews": [reviews[key] for key in sorted(reviews)],
    }
    if with_results:
        return state, results
    return state


def logical_state_hash(state: dict) -> str:
    """Stable digest of a reduced state, for comparing two replays of one ledger."""
    encoded = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
