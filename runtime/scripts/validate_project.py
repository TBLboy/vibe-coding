#!/usr/bin/env python3
"""Validate Project Log schemas, cross-references, clarification gates, and Loop state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover
    print(
        "Missing dependency. Run: python -m pip install -r scripts/requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc

from loop_state import validate_loop


DATA_SCHEMAS = {
    ".project-log/workflow.yaml": ".project-log/schemas/workflow.schema.json",
    ".project-log/business-logic/atoms.yaml": ".project-log/schemas/business-logic.schema.json",
    ".project-log/business-logic/open-questions.yaml": ".project-log/schemas/open-questions.schema.json",
    ".project-log/business-logic/clarification.yaml": ".project-log/schemas/business-clarification.schema.json",
    ".project-log/goals/active-goal.yaml": ".project-log/schemas/project-goal.schema.json",
    ".project-log/tasks/task-list.yaml": ".project-log/schemas/task-list.schema.json",
    ".project-log/decisions/decision-log.yaml": ".project-log/schemas/decision-log.schema.json",
    ".project-log/requirements/baseline.yaml": ".project-log/schemas/requirement-baseline.schema.json",
    ".project-log/research/solution-research.yaml": ".project-log/schemas/solution-research.schema.json",
    ".project-log/architecture/architecture.yaml": ".project-log/schemas/architecture.schema.json",
    ".project-log/alignment/findings.yaml": ".project-log/schemas/alignment.schema.json",
    ".project-log/verification/evidence.yaml": ".project-log/schemas/verification-evidence.schema.json",
    ".project-log/work-trace/trace.yaml": ".project-log/schemas/work-trace.schema.json",
    ".project-log/retrospective/retrospective.yaml": ".project-log/schemas/retrospective.schema.json",
    ".project-log/distillation/candidates.yaml": ".project-log/schemas/distillation.schema.json",
    ".project-log/loop/active-run.yaml": ".project-log/schemas/loop-active-run.schema.json",
    ".project-log/loop/evidence-index.yaml": ".project-log/schemas/loop-evidence-index.schema.json",
}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def schema_errors(root: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    loaded: dict[str, Any] = {}
    for data_rel, schema_rel in DATA_SCHEMAS.items():
        data_path = root / data_rel
        schema_path = root / schema_rel
        if not data_path.exists():
            errors.append(f"missing data file: {data_rel}")
            continue
        if not schema_path.exists():
            errors.append(f"missing schema file: {schema_rel}")
            continue
        try:
            data = load_yaml(data_path)
            schema = load_json(schema_path)
            loaded[data_rel] = data
            validator = Draft202012Validator(schema)
            for item in sorted(validator.iter_errors(data), key=lambda error: list(error.path)):
                location = ".".join(str(part) for part in item.path) or "<root>"
                errors.append(f"{data_rel}:{location}: {item.message}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{data_rel}: failed to load/validate: {exc}")
    return errors, loaded


def unique_ids(items: list[dict[str, Any]], label: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for item in items:
        identifier = item.get("id")
        if identifier in seen:
            errors.append(f"duplicate {label} id: {identifier}")
        if isinstance(identifier, str):
            seen.add(identifier)
    return seen


def cross_reference_errors(loaded: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    atoms = loaded.get(".project-log/business-logic/atoms.yaml", {}).get("atoms", [])
    tasks = loaded.get(".project-log/tasks/task-list.yaml", {}).get("tasks", [])
    decisions = loaded.get(".project-log/decisions/decision-log.yaml", {}).get("decisions", [])
    baselines = loaded.get(".project-log/requirements/baseline.yaml", {}).get("baselines", [])
    studies = loaded.get(".project-log/research/solution-research.yaml", {}).get("studies", [])
    architectures = loaded.get(".project-log/architecture/architecture.yaml", {}).get("architectures", [])
    findings = loaded.get(".project-log/alignment/findings.yaml", {}).get("findings", [])
    questions = loaded.get(".project-log/business-logic/open-questions.yaml", {}).get("questions", [])

    business_ids = unique_ids(atoms, "business logic", errors)
    task_ids = unique_ids(tasks, "task", errors)
    decision_ids = unique_ids(decisions, "decision", errors)
    baseline_ids = unique_ids(baselines, "requirement baseline", errors)
    unique_ids(studies, "solution research", errors)
    unique_ids(architectures, "architecture", errors)
    unique_ids(findings, "alignment finding", errors)
    question_ids = unique_ids(questions, "open question", errors)

    def require_refs(owner: str, refs: list[str], valid: set[str], kind: str) -> None:
        for reference in refs:
            if reference not in valid:
                errors.append(f"{owner}: unknown {kind} reference {reference}")

    for atom in atoms:
        owner = atom["id"]
        require_refs(owner, atom.get("dependencies", []), business_ids, "business logic")
        require_refs(owner, atom.get("decision_refs", []), decision_ids, "decision")
        require_refs(owner, atom.get("baseline_refs", []), baseline_ids, "baseline")

    for task in tasks:
        owner = task["id"]
        require_refs(owner, task.get("related_business_logic", []), business_ids, "business logic")
        require_refs(owner, task.get("related_decisions", []), decision_ids, "decision")
        require_refs(owner, task.get("depends_on", []), task_ids, "task")
        require_refs(owner, task.get("blocked_by", []), task_ids, "task")
        require_refs(owner, task.get("blocked_by_questions", []), question_ids, "open question")
        parent = task.get("parent_id")
        if parent is not None and parent not in task_ids:
            errors.append(f"{owner}: unknown parent task {parent}")
        if owner in task.get("depends_on", []):
            errors.append(f"{owner}: task cannot depend on itself")
        if task.get("status") == "done":
            verification = task.get("verification", {})
            if verification.get("status") not in {"passed", "not-applicable"}:
                errors.append(f"{owner}: done task lacks passed/not-applicable verification")

    for question in questions:
        owner = question["id"]
        require_refs(owner, question.get("related_business_logic", []), business_ids, "business logic")
        require_refs(owner, question.get("related_tasks", []), task_ids, "task")
        if question.get("authority") == "C" and question.get("status") == "answered" and not question.get("answer"):
            errors.append(f"{owner}: answered C-level question has no answer")

    for decision in decisions:
        owner = decision["id"]
        require_refs(owner, decision.get("related_tasks", []), task_ids, "task")
        require_refs(owner, decision.get("related_business_logic", []), business_ids, "business logic")
        if decision.get("authority") == "C" and decision.get("user_approval") == "not-required":
            errors.append(f"{owner}: C-level decision cannot use user_approval=not-required")

    for baseline in baselines:
        require_refs(baseline["id"], baseline.get("business_logic_refs", []), business_ids, "business logic")

    for study in studies:
        require_refs(study["id"], study.get("related_business_logic", []), business_ids, "business logic")
        require_refs(study["id"], study.get("related_tasks", []), task_ids, "task")
        reference = study.get("decision_ref")
        if reference is not None and reference not in decision_ids:
            errors.append(f"{study['id']}: unknown decision reference {reference}")

    for architecture in architectures:
        require_refs(architecture["id"], architecture.get("related_business_logic", []), business_ids, "business logic")
        require_refs(architecture["id"], architecture.get("decision_refs", []), decision_ids, "decision")

    for finding in findings:
        require_refs(finding["id"], finding.get("business_logic_refs", []), business_ids, "business logic")
        require_refs(finding["id"], finding.get("related_tasks", []), task_ids, "task")

    return errors


def clarification_gate_errors(loaded: dict[str, Any]) -> list[str]:
    workflow = loaded.get(".project-log/workflow.yaml", {})
    clarification = loaded.get(".project-log/business-logic/clarification.yaml", {})
    phase_order = workflow.get("phase_order", [])
    current = workflow.get("current_phase")
    try:
        after_clarification = phase_order.index(current) > phase_order.index("business-clarification")
    except (ValueError, AttributeError):
        return []
    if not after_clarification:
        return []
    errors: list[str] = []
    if clarification.get("gate", {}).get("status") != "passed":
        errors.append("business clarification gate must pass before requirement-baseline or later phases")
    conflicts = clarification.get("alignment", {}).get("conflicts", [])
    unresolved = [item.get("id") for item in conflicts if item.get("status") == "open"]
    if unresolved:
        errors.append("open functional/technical clarification conflicts: " + ", ".join(map(str, unresolved)))
    return errors


def validate(root: Path) -> list[str]:
    schema, loaded = schema_errors(root)
    return schema + cross_reference_errors(loaded) + clarification_gate_errors(loaded) + validate_loop(root)


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
    print("Validation passed: Project Log schemas, references, clarification gates, and Loop state are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
