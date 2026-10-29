#!/usr/bin/env python3
"""Initialize a Vibe Coding V2 project: root AGENTS.md (managed general rules + project rules) and .vibe/progress.md."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GENERAL_BEGIN = "<!-- VIBE-PROJECT-GENERAL:BEGIN -->"
GENERAL_END = "<!-- VIBE-PROJECT-GENERAL:END -->"
PROJECT_RULES_HEADING = "## 项目级规则"
PROJECT_RULES_EMPTY_HINT = "（无：初始化时未发现 README/docs 项目说明，可在此手动补充。）"
REPO_TYPE_LABEL = {"personal": "个人仓库", "team": "团队协作仓库"}
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def load_template(name: str) -> str:
    path = TEMPLATES / name
    if not path.is_file():
        raise FileNotFoundError(f"Template missing: {path}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def general_block(template: str) -> str:
    return f"{GENERAL_BEGIN}\n{template}{GENERAL_END}\n"


def project_rules_section(project_rules: str, repo_type: str | None) -> str:
    lines = [PROJECT_RULES_HEADING, ""]
    rules = (project_rules or "").strip()
    if repo_type:
        lines.append(f"仓库类型：{REPO_TYPE_LABEL[repo_type]}")
        if rules:
            lines.append("")
    lines.append(rules if rules else ("" if repo_type else PROJECT_RULES_EMPTY_HINT))
    return "\n".join(lines).rstrip("\n") + "\n"


def read_preserving_newlines(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_preserving_newlines(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)


def update_general_block(path: Path, content: str, template: str, dry_run: bool) -> str:
    """Replace only the span between the markers; everything outside keeps its bytes."""
    start = content.index(GENERAL_BEGIN)
    end = content.find(GENERAL_END, start)
    if end == -1:
        return "markers-unbalanced"
    end += len(GENERAL_END)
    if GENERAL_BEGIN in content[start + len(GENERAL_BEGIN):end]:
        return "markers-ambiguous"
    replacement = general_block(template).rstrip("\n")
    if content[start:end] == replacement:
        return "unchanged"
    if not dry_run:
        write_preserving_newlines(path, content[:start] + replacement + content[end:])
    return "updated"


def ensure_agents_md(target: Path, template: str, project_rules: str, repo_type: str | None, dry_run: bool) -> str:
    path = target / "AGENTS.md"
    if path.exists():
        content = read_preserving_newlines(path)
        if GENERAL_BEGIN in content:
            return update_general_block(path, content, template, dry_run)
        # Existing user content is preserved verbatim and treated as project-level rules.
        new_content = general_block(template) + "\n" + content
        if (project_rules.strip() or repo_type) and PROJECT_RULES_HEADING not in content:
            if not new_content.endswith("\n"):
                new_content += "\n"
            new_content += "\n" + project_rules_section(project_rules, repo_type)
        status = "injected"
    else:
        new_content = general_block(template) + "\n" + project_rules_section(project_rules, repo_type)
        status = "created"
    if not dry_run:
        write_preserving_newlines(path, new_content)
    return status


def ensure_progress(target: Path, dry_run: bool) -> str:
    path = target / ".vibe" / "progress.md"
    if path.exists():
        return "unchanged"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(load_template("progress.md"), encoding="utf-8")
    return "created"


def ensure_docs(target: Path, dry_run: bool) -> str:
    """`.vibe/docs/` holds the project's miscellaneous working documents; created at initialization."""
    path = target / ".vibe" / "docs"
    if path.is_dir():
        return "unchanged"
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").touch()
    return "created"


def find_memory_root_above(target: Path) -> Path | None:
    """Return the nearest strict ancestor that already owns a `.vibe/`, if any."""
    for ancestor in target.parents:
        if (ancestor / ".vibe").is_dir():
            return ancestor
    return None


def initialize(target: Path, project_rules: str = "", repo_type: str | None = None, dry_run: bool = False, allow_nested: bool = False) -> dict:
    target = target.expanduser().resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {target}")
    owner = find_memory_root_above(target)
    if owner is not None and not allow_nested:
        raise ValueError(
            f"Refusing to create a nested .vibe/: {owner} already owns this project's memory root. "
            "Initialize or work from that directory, or pass --allow-nested if this is intentionally a separate project."
        )
    template = load_template("general-rules.md")
    agents_status = ensure_agents_md(target, template, project_rules, repo_type, dry_run)
    progress_status = ensure_progress(target, dry_run)
    docs_status = ensure_docs(target, dry_run)
    return {
        "target": str(target),
        "agents_md": {"status": agents_status, "path": str(target / "AGENTS.md")},
        "progress_md": {"status": progress_status, "path": str(target / ".vibe" / "progress.md")},
        "docs_dir": {"status": docs_status, "path": str(target / ".vibe" / "docs")},
        "project_rules_status": "provided" if (project_rules or "").strip() else "empty",
        "repo_type": repo_type,
        "dry_run": dry_run,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--project-rules", default="", help="Project-specific rules distilled from README/docs/code")
    parser.add_argument("--repo-type", choices=sorted(REPO_TYPE_LABEL), default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-nested", action="store_true", help="permit a .vibe/ below a directory that already owns one (separate project)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = initialize(args.target, args.project_rules, args.repo_type, args.dry_run, args.allow_nested)
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Project root : {result['target']}")
        print(f"AGENTS.md    : {result['agents_md']['status']} -> {result['agents_md']['path']}")
        print(f"progress.md  : {result['progress_md']['status']} -> {result['progress_md']['path']}")
        print(f"docs/        : {result['docs_dir']['status']} -> {result['docs_dir']['path']}")
        print(f"Project rules: {result['project_rules_status']}")
        print(f"Repo type    : {result['repo_type'] or 'not recorded'}")
        print(f"Dry-run      : {result['dry_run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
