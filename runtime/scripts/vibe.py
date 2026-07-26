#!/usr/bin/env python3
"""Small local utilities for the Vibe Workflow project log."""

from __future__ import annotations

import argparse
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
    next_parser = sub.add_parser("next-id")
    next_parser.add_argument("kind", choices=["task", "logic", "decision", "alignment", "knowledge", "question"])
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
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
