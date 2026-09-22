#!/usr/bin/env python3
"""Initialize a project: create .project-log via the existing chain and establish or safely update root AGENTS.md."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

GENERAL_BEGIN = "<!-- VIBE-PROJECT-GENERAL:BEGIN -->"
GENERAL_END = "<!-- VIBE-PROJECT-GENERAL:END -->"
PROJECT_RULES_EMPTY_HINT = "（无：初始化时未发现 README/docs 项目说明，可在此手动补充。）"


def find_init_project_py() -> Path:
    candidates = []
    env_runtime = os.environ.get("VIBE_RUNTIME")
    if env_runtime:
        candidates.append(Path(env_runtime) / "scripts" / "init_project.py")
    opencode_config = Path(
        os.environ.get("OPENCODE_CONFIG_DIR")
        or (Path.home() / ".config" / "opencode")
    )
    candidates.append(opencode_config / "vibe-workflow" / "scripts" / "init_project.py")
    candidates.append(Path(__file__).resolve().parents[3] / "runtime" / "scripts" / "init_project.py")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Vibe runtime init_project.py not found")


def load_general_template() -> str:
    template = Path(__file__).resolve().parent.parent / "templates" / "general-rules.md"
    if not template.is_file():
        raise FileNotFoundError(f"General rules template missing: {template}")
    return template.read_text(encoding="utf-8").strip() + "\n"


def general_block(template: str) -> str:
    return f"{GENERAL_BEGIN}\n{template}{GENERAL_END}\n"


def build_agents_md(template: str, project_rules: str) -> str:
    block = general_block(template)
    rules = (project_rules or "").strip()
    if rules:
        project_section = f"## 项目级规则\n\n{rules}\n"
    else:
        project_section = f"## 项目级规则\n\n{PROJECT_RULES_EMPTY_HINT}\n"
    return block + "\n" + project_section


def ensure_agents_md(target: Path, template: str, project_rules: str, dry_run: bool) -> str:
    path = target / "AGENTS.md"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if GENERAL_BEGIN in content:
            return "skipped"
        new_content = general_block(template) + "\n" + content
        status = "injected"
    else:
        new_content = build_agents_md(template, project_rules)
        status = "created"
    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return status


def initialize(target: Path, project_rules: str = "", dry_run: bool = False) -> dict:
    target = target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    init_project_py = find_init_project_py()
    sys.path.insert(0, str(init_project_py.parent))
    import init_project  # existing chain, unchanged

    project_log_existed = (target / ".project-log").exists()
    created, skipped = init_project.initialize_project(target, dry_run=dry_run)
    project_log_status = "skipped" if project_log_existed else "created"

    template = load_general_template()
    agents_status = ensure_agents_md(target, template, project_rules, dry_run)

    return {
        "target": str(target),
        "project_log": {
            "status": project_log_status,
            "created": [str(p) for p in created],
            "skipped": [str(p) for p in skipped],
        },
        "agents_md": {"status": agents_status, "path": str(target / "AGENTS.md")},
        "project_rules_status": "provided" if (project_rules or "").strip() else "empty",
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--project-rules", default="", help="Project-specific rules extracted from README/docs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = initialize(args.target, args.project_rules, args.dry_run)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        pl = result["project_log"]
        agents = result["agents_md"]
        rules = result["project_rules_status"]
        print(f"Project root : {result['target']}")
        print(f"Project Log  : {pl['status']} (created {len(pl['created'])}, skipped {len(pl['skipped'])})")
        print(f"AGENTS.md    : {agents['status']} -> {agents['path']}")
        print(f"Project rules: {rules}")
        print(f"Dry-run      : {result['dry_run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
