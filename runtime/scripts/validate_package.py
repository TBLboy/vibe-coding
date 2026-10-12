#!/usr/bin/env python3
"""Validate the Vibe Coding package (OpenCode client surface) before installation or release."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print("Missing dependency: PyYAML", file=sys.stderr)
    raise SystemExit(2) from exc

from framework_info import VERSION


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER = {"name", "description", "license", "compatibility", "metadata"}
REQUIRED_RUNTIME = {
    "scripts/framework_info.py",
    "scripts/state_store.py",
    "scripts/state_replay.py",
    "scripts/state_ledger.py",
    "scripts/state_views.py",
    "scripts/state_context.py",
    "scripts/state_routing.py",
    "scripts/state_evidence.py",
    "scripts/state_gate.py",
    "vibe.ps1",
    "vibe.sh",
    "scripts/vibe_python.ps1",
    "scripts/vibe_python.sh",
    "scripts/init_project.py",
    "scripts/validate_package.py",
    "scripts/validate_project.py",
    "project-log-template/current-session.md",
    "project-log-template/progress.md",
    "project-log-template/docs/archive/README.md",
}
REQUIRED_OPENCODE = {
    "install.sh",
    "AGENTS.md",
    "opencode.json",
    "agents/vibe-main.md",
    "agents/business-analyst.md",
    "agents/codebase-onboarder.md",
    "agents/solution-researcher.md",
    "agents/implementation-builder.md",
    "agents/verification-reviewer.md",
    "agents/alignment-reviewer.md",
    "agents/paper-reader.md",
    "agents/workflow-distiller.md",
    "commands/vibe-start.md",
    "commands/vibe-resume.md",
    "commands/vibe-plan.md",
    "commands/vibe-implement.md",
    "commands/vibe-verify.md",
    "commands/vibe-status.md",
    "commands/vibe-retro.md",
    "plugins/vibe-workflow/index.ts",
}
REQUIRED_PACKAGE_FILES = {
    "AI_INSTALL.md",
    "AI_UPGRADE.md",
    "README.md",
    "docs/RELEASE-NOTES.md",
    "scripts/opencode_installer.py",
}


def parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated YAML frontmatter")
    data = yaml.safe_load(text[4:end])
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skills_root = root / "skills"
    skill_names: set[str] = set()
    for path in sorted(skills_root.glob("*/SKILL.md")):
        try:
            metadata = parse_frontmatter(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue
        expected = path.parent.name
        name = metadata.get("name")
        if name != expected:
            errors.append(f"{path.relative_to(root)}: name {name!r} does not match directory {expected!r}")
        if not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name):
            errors.append(f"{path.relative_to(root)}: invalid skill name")
        else:
            skill_names.add(name)
        description = metadata.get("description")
        if not isinstance(description, str) or not (1 <= len(description) <= 1024):
            errors.append(f"{path.relative_to(root)}: description must be 1-1024 chars")
        unknown = sorted(set(metadata) - ALLOWED_FRONTMATTER)
        if unknown:
            errors.append(f"{path.relative_to(root)}: unsupported frontmatter fields: {unknown}")

    if not skill_names:
        errors.append("package contains no Skills")
    for relative in sorted(REQUIRED_PACKAGE_FILES):
        if not (root / relative).is_file():
            errors.append(f"missing package file: {relative}")
    for relative in sorted(REQUIRED_RUNTIME):
        if not (root / "runtime" / relative).is_file():
            errors.append(f"missing runtime asset: runtime/{relative}")
    for relative in sorted(REQUIRED_OPENCODE):
        if not (root / "runtime" / "opencode" / relative).is_file():
            errors.append(f"missing OpenCode asset: runtime/opencode/{relative}")

    release_notes = root / "docs/RELEASE-NOTES.md"
    if release_notes.is_file() and VERSION not in release_notes.read_text(encoding="utf-8"):
        errors.append(f"docs/RELEASE-NOTES.md does not document the current version {VERSION}")

    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        if ".opencode/commands" in text or ".opencode/agents" in text or ".opencode/skills" in text:
            errors.append(f"{path.relative_to(root)} contains obsolete OpenCode metadata validation")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = validate(args.root.expanduser().resolve())
    if errors:
        print(f"Package validation failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
