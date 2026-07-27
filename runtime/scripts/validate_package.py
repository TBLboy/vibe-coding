#!/usr/bin/env python3
"""Validate the Codex Vibe Coding package before installation or release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print("Missing dependency: PyYAML", file=sys.stderr)
    raise SystemExit(2) from exc


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER = {"name", "description", "license", "compatibility", "metadata"}
REQUIRED_RUNTIME = {
    "scripts/init_project.py",
    "scripts/loop_state.py",
    "scripts/loopctl.py",
    "scripts/render_subagent_prompt.py",
    "scripts/validate_package.py",
    "scripts/validate_project.py",
    "hooks/hook_common.py",
    "hooks/session_start.py",
    "hooks/post_tool_use.py",
    "hooks/pre_compact.py",
    "agents/roles.json",
    "mcp/optional-mcps.json",
    "project-log-template/workflow.yaml",
    "project-log-template/business-logic/clarification.yaml",
    "project-log-template/goals/active-goal.yaml",
    "project-log-template/loop/active-run.yaml",
    "project-log-template/loop/evidence-index.yaml",
}
REQUIRED_PACKAGE_FILES = {
    "AI_INSTALL.md",
    "AI_UPGRADE.md",
    "README.md",
    "install.ps1",
    "install.sh",
    "update.ps1",
    "update.sh",
    "uninstall.ps1",
    "uninstall.sh",
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

    roles_path = root / "runtime/agents/roles.json"
    if roles_path.is_file():
        try:
            roles = json.loads(roles_path.read_text(encoding="utf-8")).get("roles", {})
            templates = {path.stem for path in (root / "runtime/agents").glob("*.md") if path.name != "README.md"}
            for role, metadata in roles.items():
                if role not in templates:
                    errors.append(f"role has no template: {role}")
                if metadata.get("skill") not in skill_names:
                    errors.append(f"role {role} references unknown Skill {metadata.get('skill')!r}")
            for template in sorted(templates - set(roles)):
                errors.append(f"role template is not registered: {template}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"failed to validate roles.json: {exc}")

    catalog_path = root / "runtime/mcp/optional-mcps.json"
    if catalog_path.is_file():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            entries = catalog.get("mcps") if isinstance(catalog, dict) else None
            if not isinstance(entries, list) or not entries:
                errors.append("optional MCP catalog must contain a non-empty 'mcps' list")
            else:
                names: set[str] = set()
                for entry in entries:
                    if not isinstance(entry, dict):
                        errors.append("optional MCP catalog contains a non-object entry")
                        continue
                    name = entry.get("name")
                    kind = entry.get("kind")
                    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                        errors.append(f"optional MCP catalog has invalid name: {name!r}")
                    elif name in names:
                        errors.append(f"optional MCP catalog has duplicate name: {name}")
                    else:
                        names.add(name)
                    if kind == "codex-stdio":
                        command = entry.get("command")
                        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
                            errors.append(f"optional MCP {name!r} has invalid command")
                    elif kind == "codex-plugin":
                        if not isinstance(entry.get("plugin"), str):
                            errors.append(f"optional MCP {name!r} is missing plugin")
                    else:
                        errors.append(f"optional MCP {name!r} has unsupported kind: {kind!r}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"failed to validate optional MCP catalog: {exc}")

    plugin_manifest = root / "plugins/vibe-toolbelt/.codex-plugin/plugin.json"
    marketplace = root / ".agents/plugins/marketplace.json"
    if not plugin_manifest.is_file():
        errors.append("missing optional plugin manifest")
    if not marketplace.is_file():
        errors.append("missing local marketplace manifest")

    prompt = root / "prompts/vibe-global-agent.md"
    if not prompt.is_file():
        errors.append("missing global agent prompt")
    elif ".opencode/" in prompt.read_text(encoding="utf-8"):
        errors.append("global prompt contains obsolete .opencode path")

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
