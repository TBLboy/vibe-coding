#!/usr/bin/env python3
"""Deterministic state operations for the Vibe Loop Core."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Iterator

import yaml


EVENT_TYPES = {
    "run-started",
    "task-selected",
    "work-unit-started",
    "work-unit-finished",
    "evidence-recorded",
    "evidence-invalidated",
    "review-completed",
    "loop-decision",
    "user-decision-recorded",
    "limit-reached",
    "handoff-generated",
    "run-completed",
    "native-goal-bound",
    "native-goal-state-observed",
    "native-goal-unbound",
    "state-repaired",
}
EVIDENCE_STATES = {"candidate", "valid", "failed", "stale", "superseded", "invalid"}
FAILURE_ORIGINS = {
    "implementation",
    "specification",
    "task-decomposition",
    "technical-selection",
    "functional-business-logic",
    "technical-business-logic",
    "environment",
    "verification-harness",
    "unknown",
}
DECISION_ACTIONS = {
    "retry-current-task",
    "return-to-phase",
    "next-task",
    "next-phase",
    "repair-environment",
    "repair-harness",
    "targeted-research",
    "goal-complete",
    "handoff",
}
NATIVE_GOAL_STATES = {
    "active",
    "paused",
    "blocked",
    "budget-limited",
    "usage-limited",
    "complete",
    "cleared",
    "replaced",
}
PHASES = {
    "business-intent",
    "business-clarification",
    "requirement-baseline",
    "solution-research",
    "architecture-decision",
    "task-decomposition",
    "engineering-spec",
    "implementation",
    "verification",
    "alignment",
    "retrospective",
    "distillation",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_log(root: Path) -> Path:
    return root / ".project-log"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping: {path}")
    return data


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


@contextmanager
def file_lock(path: Path, timeout: float = 5.0) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + timeout
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {lock_path}")
            time.sleep(0.05)
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def runtime_template() -> Path:
    return Path(__file__).resolve().parents[1] / "project-log-template"


def initialize_loop(root: Path) -> list[str]:
    log = project_log(root)
    if not log.is_dir():
        raise FileNotFoundError(f"project log is missing: {log}")
    created: list[str] = []
    for relative in (
        Path("business-logic/clarification.yaml"),
        Path("goals/active-goal.yaml"),
        Path("loop/active-run.yaml"),
        Path("loop/events.jsonl"),
        Path("loop/evidence-index.yaml"),
        Path("loop/handoff.md"),
        Path("schemas/business-clarification.schema.json"),
        Path("schemas/project-goal.schema.json"),
        Path("schemas/loop-active-run.schema.json"),
        Path("schemas/loop-evidence-index.schema.json"),
    ):
        source = runtime_template() / relative
        destination = log / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        created.append(relative.as_posix())
    return created


def active_run_path(root: Path) -> Path:
    return project_log(root) / "loop/active-run.yaml"


def events_path(root: Path) -> Path:
    return project_log(root) / "loop/events.jsonl"


def evidence_path(root: Path) -> Path:
    return project_log(root) / "loop/evidence-index.yaml"


def goal_path(root: Path) -> Path:
    return project_log(root) / "goals/active-goal.yaml"


def load_active_run(root: Path) -> dict[str, Any]:
    return load_yaml(active_run_path(root))


def save_active_run(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    save_yaml(active_run_path(root), state)


def read_events(root: Path, tolerate_bad_tail: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    path = events_path(root)
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            message = f"{path}:{index}: invalid JSON: {exc}"
            if tolerate_bad_tail and index == len(lines):
                errors.append(message)
                break
            errors.append(message)
            continue
        if not isinstance(event, dict):
            errors.append(f"{path}:{index}: event must be an object")
            continue
        events.append(event)
    return events, errors


def repair_bad_event_tail(root: Path) -> list[str]:
    path = events_path(root)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    valid: list[str] = []
    warnings: list[str] = []
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            if index != len(lines):
                raise ValueError(f"{path}:{index}: invalid non-tail JSON: {exc}") from exc
            quarantine = path.with_name(f"events.corrupt-{int(time.time())}.json")
            atomic_write_text(quarantine, line + "\n")
            atomic_write_text(path, "\n".join(valid) + ("\n" if valid else ""))
            warnings.append(f"quarantined invalid event tail to {quarantine.name}")
            break
        valid.append(line)
    return warnings


def default_active_run() -> dict[str, Any]:
    return load_yaml(runtime_template() / "loop/active-run.yaml")


def restore_active_run(root: Path, force: bool = False) -> tuple[dict[str, Any], list[str]]:
    warnings = repair_bad_event_tail(root)
    path = active_run_path(root)
    if path.is_file() and not force:
        try:
            return load_active_run(root), warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"active-run could not be loaded and will be rebuilt: {exc}")
    state = default_active_run()
    events, errors = read_events(root)
    if errors:
        raise ValueError("; ".join(errors))
    for event in events:
        snapshot = event.get("state_after")
        if isinstance(snapshot, dict):
            state = copy.deepcopy(snapshot)
        elif event.get("type") == "run-started":
            state["run_id"] = event.get("run_id")
            state["goal_id"] = event.get("goal_id")
            state["phase"] = event.get("phase") or state["phase"]
        elif event.get("type") == "task-selected":
            state["task_id"] = event.get("task_id")
        elif event.get("type") == "handoff-generated":
            state["status"] = "handed-off"
        elif event.get("type") == "run-completed":
            state["status"] = "complete"
        state["last_event_id"] = event.get("event_id")
    save_active_run(root, state)
    if events:
        repaired = append_event(root, "state-repaired", {"reason": "active-run rebuilt from events"})
        state = load_active_run(root)
        warnings.append(f"active-run rebuilt; repair event {repaired['event_id']} appended")
    return state, warnings


def next_event_id(events: list[dict[str, Any]]) -> str:
    maximum = 0
    for event in events:
        identifier = str(event.get("event_id", ""))
        if identifier.startswith("LE-") and identifier[3:].isdigit():
            maximum = max(maximum, int(identifier[3:]))
    return f"LE-{maximum + 1:06d}"


def append_event(root: Path, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported event type: {event_type}")
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        events, errors = read_events(root, tolerate_bad_tail=True)
        if errors:
            raise ValueError(errors[-1])
        state = load_active_run(root)
        event = {
            "schema_version": 1,
            "event_id": next_event_id(events),
            "time": utc_now(),
            "run_id": state.get("run_id"),
            "type": event_type,
        }
        if payload:
            reserved = {"schema_version", "event_id", "time", "run_id", "type"}.intersection(payload)
            if reserved:
                raise ValueError("event payload uses reserved fields: " + ", ".join(sorted(reserved)))
            event.update(payload)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        state["last_event_id"] = event["event_id"]
        save_active_run(root, state)
        return event


def normalize_project_path(root: Path, value: str) -> str:
    path = Path(value)
    absolute = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        return absolute.relative_to(root.resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_git(root: Path, arguments: list[str]) -> str | None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def version_binding(root: Path, files: list[str]) -> dict[str, Any]:
    normalized = [normalize_project_path(root, item) for item in files]
    commit = run_git(root, ["rev-parse", "HEAD"])
    diff_args = ["diff", "--binary", "--no-ext-diff", "HEAD"]
    if normalized:
        diff_args.extend(["--", *normalized])
    diff = run_git(root, diff_args)
    hashes: dict[str, str] = {}
    for item in normalized:
        path = root / item
        if path.is_file():
            hashes[item] = file_sha256(path)
    return {
        "git_commit": commit,
        "diff_hash": hashlib.sha256((diff or "").encode("utf-8")).hexdigest() if commit else None,
        "file_hashes": hashes,
    }


def record_evidence(
    root: Path,
    *,
    evidence_id: str,
    kind: str,
    subject: str,
    status: str,
    files: list[str],
    requirements: list[str],
    tasks: list[str],
    command: str | None,
    result_ref: str | None,
    replace: bool = False,
) -> dict[str, Any]:
    if status not in EVIDENCE_STATES:
        raise ValueError(f"unsupported evidence status: {status}")
    path = evidence_path(root)
    with file_lock(path):
        index = load_yaml(path)
        items = index.setdefault("evidence", [])
        existing = next((item for item in items if item.get("id") == evidence_id), None)
        if existing and not replace:
            raise ValueError(f"evidence already exists: {evidence_id}")
        item = {
            "id": evidence_id,
            "kind": kind,
            "subject": subject,
            "status": status,
            "command": command,
            "result_ref": result_ref,
            "covers": {
                "files": [normalize_project_path(root, value) for value in files],
                "requirements": requirements,
                "tasks": tasks,
            },
            "version_binding": version_binding(root, files),
            "recorded_at": utc_now(),
            "invalidated_at": None,
            "invalidation_reason": None,
        }
        if existing:
            items[items.index(existing)] = item
        else:
            items.append(item)
        save_yaml(path, index)
    append_event(root, "evidence-recorded", {"evidence_id": evidence_id, "status": status})
    return item


def invalidate_evidence(root: Path, changed_paths: list[str], reason: str) -> list[str]:
    normalized = {normalize_project_path(root, item) for item in changed_paths}
    if not normalized:
        return []
    path = evidence_path(root)
    invalidated: list[str] = []
    with file_lock(path):
        index = load_yaml(path)
        for item in index.get("evidence", []):
            if item.get("status") not in {"candidate", "valid"}:
                continue
            covered = set(item.get("covers", {}).get("files", []))
            if normalized and not covered.intersection(normalized):
                continue
            item["status"] = "stale"
            item["invalidated_at"] = utc_now()
            item["invalidation_reason"] = reason
            invalidated.append(str(item.get("id")))
        if invalidated:
            save_yaml(path, index)
    for evidence_id in invalidated:
        append_event(
            root,
            "evidence-invalidated",
            {"evidence_id": evidence_id, "changed_paths": sorted(normalized), "reason": reason},
        )
    return invalidated


def open_c_questions(root: Path) -> list[str]:
    path = project_log(root) / "business-logic/open-questions.yaml"
    if not path.is_file():
        return []
    questions = load_yaml(path).get("questions", [])
    return [
        str(question.get("id"))
        for question in questions
        if question.get("status") == "open" and question.get("authority") == "C"
    ]


def evaluate_goal(root: Path) -> dict[str, Any]:
    document = load_yaml(goal_path(root))
    goal = document.get("goal")
    if not goal:
        return {"passed": False, "reasons": ["project goal is not defined"]}
    evidence_items = load_yaml(evidence_path(root)).get("evidence", [])
    evidence = {str(item.get("id")): item for item in evidence_items}
    reasons: list[str] = []
    for condition in goal.get("success_conditions", []):
        status = condition.get("status")
        references = condition.get("evidence_refs", [])
        if status not in {"passed", "not-applicable"}:
            reasons.append(f"{condition.get('id')}: success condition is {status}")
        if status == "passed" and not references:
            reasons.append(f"{condition.get('id')}: passed condition has no evidence")
        for reference in references:
            if evidence.get(reference, {}).get("status") != "valid":
                reasons.append(f"{condition.get('id')}: evidence {reference} is not valid")
    for requirement in goal.get("required_evidence", []):
        references = requirement.get("evidence_refs", [])
        if not references:
            reasons.append(f"required evidence missing: {requirement.get('subject')}")
        for reference in references:
            if evidence.get(reference, {}).get("status") != "valid":
                reasons.append(f"required evidence {reference} is not valid")
    questions = open_c_questions(root)
    if questions:
        reasons.append("open C-level questions: " + ", ".join(questions))
    if goal.get("risk_level") in {"high", "critical"}:
        reviewer = [
            item
            for item in evidence_items
            if item.get("kind") == "review"
            and item.get("subject") == "goal-final-review"
            and item.get("status") == "valid"
        ]
        if not reviewer:
            reasons.append("high-risk goal lacks valid independent review evidence")
    return {"passed": not reasons, "goal_id": goal.get("id"), "reasons": reasons}


def project_goal_summary(root: Path) -> str:
    goal = load_yaml(goal_path(root)).get("goal")
    if not goal:
        raise ValueError("project goal is not defined")
    conditions = "; ".join(item.get("statement", "") for item in goal.get("success_conditions", []))
    return f"{goal['statement']} Success conditions: {conditions} Project Goal: {goal['id']}."


def sync_native_goal(root: Path, status: str, thread_goal_id: str | None = None) -> dict[str, Any]:
    if status not in NATIVE_GOAL_STATES:
        raise ValueError(f"unsupported native goal status: {status}")
    state = load_active_run(root)
    native = state.setdefault("native_goal", {})
    native["thread_goal_id"] = thread_goal_id or native.get("thread_goal_id")
    native["last_known_status"] = status
    native["last_synced_at"] = utc_now()
    if status in {"cleared", "replaced"}:
        native["binding_status"] = "unbound"
    else:
        native["binding_status"] = "bound"
    if status == "active":
        state["status"] = "active"
    elif status == "paused":
        state["status"] = "handed-off"
    elif status == "blocked":
        state["status"] = "blocked"
    elif status in {"budget-limited", "usage-limited"}:
        state["status"] = "handed-off"
    elif status == "complete":
        state["status"] = "completing"
    save_active_run(root, state)
    event_type = "native-goal-unbound" if status in {"cleared", "replaced"} else "native-goal-state-observed"
    event = append_event(root, event_type, {"native_goal_status": status, "thread_goal_id": thread_goal_id})
    return {"state": state, "event": event}


def previous_decision(root: Path, task_id: str | None) -> dict[str, Any] | None:
    events, _ = read_events(root)
    for event in reversed(events):
        if event.get("type") != "loop-decision":
            continue
        decision = event.get("decision_payload")
        if isinstance(decision, dict) and decision.get("subject", {}).get("task_id") == task_id:
            return decision
    return None


def apply_decision(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    assessment = payload.get("assessment", {})
    decision = payload.get("decision", {})
    action = decision.get("action")
    origin = assessment.get("failure_origin")
    if action not in DECISION_ACTIONS:
        raise ValueError(f"unsupported decision action: {action}")
    if assessment.get("result") == "failed" and origin is None:
        raise ValueError("failed assessment requires failure_origin")
    if origin is not None and origin not in FAILURE_ORIGINS:
        raise ValueError(f"unsupported failure origin: {origin}")
    state = load_active_run(root)
    task_id = payload.get("subject", {}).get("task_id")
    if action == "retry-current-task":
        contract = payload.get("retry_contract") or {}
        missing = [key for key in ("hypothesis", "delta", "expected_evidence") if not contract.get(key)]
        if missing:
            raise ValueError("retry contract missing: " + ", ".join(missing))
        previous = previous_decision(root, task_id)
        if previous:
            previous_contract = previous.get("retry_contract") or {}
            same_signature = previous.get("assessment", {}).get("failure_signature") == assessment.get("failure_signature")
            same_delta = previous_contract.get("delta") == contract.get("delta")
            if same_signature and same_delta:
                raise ValueError("no-change retry rejected: failure signature and delta match the previous retry")
        counters = state["counters"]
        limits = state["limits"]
        if counters["task_attempts"] >= limits["task_attempts"]:
            raise ValueError("task attempt limit reached; handoff is required")
        if counters["same_failure_count"] >= limits["same_failure_count"]:
            raise ValueError("same failure limit reached; handoff or return-to-phase is required")
        if counters["no_progress_count"] >= limits["no_progress_count"]:
            raise ValueError("no-progress limit reached; handoff or targeted research is required")
        counters["task_attempts"] += 1
        if previous and previous.get("assessment", {}).get("failure_signature") == assessment.get("failure_signature"):
            counters["same_failure_count"] += 1
        else:
            counters["same_failure_count"] = 1
        counters["no_progress_count"] = 0 if assessment.get("new_information") else counters["no_progress_count"] + 1
    state["counters"]["loop_decisions"] += 1
    if state["counters"]["loop_decisions"] > state["limits"]["loop_decisions"]:
        raise ValueError("loop decision limit reached; handoff is required")
    if action == "return-to-phase":
        target = decision.get("target_phase")
        if target not in PHASES:
            raise ValueError("return-to-phase requires decision.target_phase")
        state["phase"] = target
        state["clarification_domain"] = None
        if target == "business-clarification":
            domain = decision.get("target_domain")
            expected = {
                "functional-business-logic": "functional-business-logic",
                "technical-business-logic": "technical-business-logic",
            }.get(origin)
            if expected and domain != expected:
                raise ValueError(f"{origin} return requires decision.target_domain={expected}")
            if domain not in {
                "functional-business-logic",
                "technical-business-logic",
                "functional-technical-alignment",
            }:
                raise ValueError("business-clarification return requires a valid decision.target_domain")
            state["clarification_domain"] = domain
    elif action == "handoff":
        state["status"] = "handed-off"
    elif action == "goal-complete":
        result = evaluate_goal(root)
        if not result["passed"]:
            raise ValueError("goal completion rejected: " + "; ".join(result["reasons"]))
        state["status"] = "complete"
        goal_document = load_yaml(goal_path(root))
        if goal_document.get("goal"):
            goal_document["goal"]["status"] = "complete"
            goal_document["goal"]["updated_at"] = utc_now()
            save_yaml(goal_path(root), goal_document)
    next_action = decision.get("next_action")
    if isinstance(next_action, dict):
        state["next_action"] = next_action
    save_active_run(root, state)
    event = append_event(
        root,
        "loop-decision",
        {
            "decision_id": payload.get("decision_id"),
            "task_id": task_id,
            "decision_payload": payload,
            "state_after": state,
        },
    )
    if action == "goal-complete":
        append_event(root, "run-completed", {"goal_id": state.get("goal_id")})
    return {"state": state, "event": event}


def generate_handoff(root: Path) -> str:
    state = load_active_run(root)
    goal = load_yaml(goal_path(root)).get("goal")
    evidence = load_yaml(evidence_path(root)).get("evidence", [])
    valid = [item.get("id") for item in evidence if item.get("status") == "valid"]
    stale = [item.get("id") for item in evidence if item.get("status") == "stale"]
    next_action = state.get("next_action") or {}
    lines = [
        "# Loop Handoff",
        "",
        f"- Goal: {goal.get('id') + ' - ' + goal.get('statement') if goal else 'not set'}",
        f"- Phase: {state.get('phase')}",
        f"- Task: {state.get('task_id') or 'none'}",
        f"- Run status: {state.get('status')}",
        f"- Native Goal: {state.get('native_goal', {}).get('last_known_status') or state.get('native_goal', {}).get('binding_status')}",
        f"- Valid evidence: {', '.join(valid) if valid else 'none'}",
        f"- Stale evidence: {', '.join(stale) if stale else 'none'}",
        f"- Open C questions: {', '.join(open_c_questions(root)) or 'none'}",
        f"- Next action: {next_action.get('statement') or 'not set'}",
        "",
        "## Counters",
        "",
    ]
    for key, value in state.get("counters", {}).items():
        lines.append(f"- {key}: {value}/{state.get('limits', {}).get(key)}")
    text = "\n".join(lines).rstrip() + "\n"
    atomic_write_text(project_log(root) / "loop/handoff.md", text)
    append_event(root, "handoff-generated", {"reason": state.get("status")})
    return text


def validate_loop(root: Path) -> list[str]:
    errors: list[str] = []
    events, event_errors = read_events(root)
    errors.extend(event_errors)
    seen: set[str] = set()
    for event in events:
        event_id = event.get("event_id")
        if event_id in seen:
            errors.append(f"duplicate loop event id: {event_id}")
        if isinstance(event_id, str):
            seen.add(event_id)
        if event.get("type") not in EVENT_TYPES:
            errors.append(f"{event_id}: unsupported event type {event.get('type')}")
    try:
        state = load_active_run(root)
        if state.get("last_event_id") and state["last_event_id"] not in seen:
            errors.append(f"active-run references missing event: {state['last_event_id']}")
        for key, value in state.get("counters", {}).items():
            limit = state.get("limits", {}).get(key)
            if isinstance(limit, int) and value > limit and state.get("status") not in {"handed-off", "complete"}:
                errors.append(f"counter {key} exceeds limit without handoff")
    except Exception as exc:
        errors.append(f"failed to load active-run: {exc}")
    try:
        evidence = load_yaml(evidence_path(root)).get("evidence", [])
        identifiers: set[str] = set()
        for item in evidence:
            identifier = item.get("id")
            if identifier in identifiers:
                errors.append(f"duplicate evidence id: {identifier}")
            if isinstance(identifier, str):
                identifiers.add(identifier)
            if item.get("status") not in EVIDENCE_STATES:
                errors.append(f"{identifier}: unsupported evidence status")
    except Exception as exc:
        errors.append(f"failed to load evidence index: {exc}")
    return errors
