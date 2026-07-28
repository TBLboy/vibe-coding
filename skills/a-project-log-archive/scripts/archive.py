#!/usr/bin/env python3
"""Archive .project-log to the centralized knowledge base and push."""

import argparse, os, shutil, subprocess, sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "scripts" / "kb_path.conf"
PLACEHOLDER = "__UNSET__"

def get_kb_base() -> Path:
    """Read the KB path from config, or report unconfigured."""
    if not CONFIG.exists():
        print(f"CONFIG MISSING: {CONFIG} not found.", file=sys.stderr)
        print("Ask the user for the absolute path to their My_knowledge_base.", file=sys.stderr)
        sys.exit(2)
    raw = CONFIG.read_text().strip()
    if raw == PLACEHOLDER or not raw:
        print(f"CONFIG UNCONFIGURED: {CONFIG} contains placeholder.", file=sys.stderr)
        print("Ask the user for the absolute path to their My_knowledge_base.", file=sys.stderr)
        sys.exit(2)
    return Path(raw)

def git_push(kb_root: Path, project_name: str):
    """Stage, commit, and push the knowledge base."""
    cwd = os.getcwd()
    try:
        os.chdir(kb_root)
        subprocess.run(["git", "add", "-A"], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False)
        if result.returncode == 0:
            print("No changes to commit in knowledge base.")
            return
        subprocess.run(["git", "commit", "-m", f"archive: {project_name}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Knowledge base pushed.")
    finally:
        os.chdir(cwd)

def main():
    kb_base = get_kb_base()  # check config first
    parser = argparse.ArgumentParser(description="Archive project log to knowledge base")
    parser.add_argument("--project-root", required=True, help="Path to project root")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    src = root / ".project-log"

    if not src.is_dir():
        print(f"ERROR: .project-log not found in {root}", file=sys.stderr)
        sys.exit(1)

    kb_base = get_kb_base()
    kb_engineering = kb_base / "工程记录"
    if not kb_engineering.is_dir():
        print(f"ERROR: 工程记录/ not found under {kb_base}", file=sys.stderr)
        sys.exit(1)

    project_name = root.name
    dst_project = kb_engineering / project_name
    dst_log = dst_project / ".project-log"

    # Collision check
    if dst_project.exists() and not dst_log.exists() and any(dst_project.iterdir()):
        print(f"WARNING: {dst_project} exists with unrelated content. Skipping.", file=sys.stderr)
        sys.exit(1)

    # Remove old
    if dst_log.exists():
        print(f"Removing old: {dst_log}")
        shutil.rmtree(dst_log)

    # Copy
    dst_project.mkdir(parents=True, exist_ok=True)
    print(f"Copying {src} -> {dst_log}")
    shutil.copytree(src, dst_log)

    count = sum(1 for _ in dst_log.rglob("*") if _.is_file())
    print(f"Done. {count} files archived to {dst_log}")

    # Push
    print("Pushing knowledge base...")
    git_push(kb_base, project_name)

if __name__ == "__main__":
    main()
