#!/usr/bin/env python3
"""Archive .project-log to the centralized knowledge base and push.

Archiving is a merge, never a replacement:

* The Git ledger is merged by ``command_id``: the knowledge base copy must already
  be an exact prefix of the local ledger, so only the new tail is ever added.
* ``.state/`` (the local SQLite cache), Git internals, ``.migration/`` scratch space
  and ``legacy/new-writes/`` rollback bundles are never copied.
* The project identity in ``state-format.json`` must match, so two unrelated
  projects that share a folder name can never silently overwrite each other.
* Re-running the archive is idempotent.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "scripts" / "kb_path.conf"
PLACEHOLDER = "__UNSET__"
LEDGER_RELATIVE = Path("ledger") / "v1" / "ledger.jsonl"
MARKER = "state-format.json"
# Machine-local or derivable: never archived.
EXCLUDED_NAMES = {".state", ".git", ".migration", "new-writes", "ledger"}


class ArchiveError(RuntimeError):
    """A condition the operator must resolve before archiving can continue."""


def get_kb_base() -> Path:
    """Read the KB path from config, or report unconfigured."""
    if not CONFIG.exists():
        raise ArchiveError(
            f"CONFIG MISSING: {CONFIG} not found. Ask the user for the absolute path "
            "to their My_knowledge_base."
        )
    raw = CONFIG.read_text().strip()
    if raw == PLACEHOLDER or not raw:
        raise ArchiveError(
            f"CONFIG UNCONFIGURED: {CONFIG} contains the placeholder. Ask the user for "
            "the absolute path to their My_knowledge_base."
        )
    return Path(raw).expanduser()


def read_project_id(log: Path) -> str | None:
    """The project identity recorded in a Project Log marker, or None when absent."""
    marker = log / MARKER
    if not marker.is_file():
        return None
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ArchiveError(f"{marker} is not readable JSON: {error}") from error
    if type(document) is not dict:
        raise ArchiveError(f"{marker} is not a JSON object")
    identifier = document.get("project_id")
    if identifier is not None and type(identifier) is not str:
        raise ArchiveError(f"{marker} has a non-string project_id")
    return identifier


def read_ledger(path: Path) -> list[dict]:
    """Parse a ledger file into its events, or an empty list when it is absent."""
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ArchiveError(f"cannot read ledger {path}: {error}") from error
    events: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise ArchiveError(f"{path}:{number} is not valid JSON: {error}") from error
        if type(event) is not dict or "command_id" not in event:
            raise ArchiveError(f"{path}:{number} is not a ledger event")
        events.append(event)
    return events


def verify_ledger_superset(local: Path, kb: Path) -> dict:
    """Refuse unless the KB ledger is an exact prefix of the local ledger.

    Returns the number of local-only commands, which is the tail the archive adds.
    """
    local_events = read_ledger(local)
    kb_events = read_ledger(kb)
    if len(kb_events) > len(local_events):
        raise ArchiveError(
            f"the knowledge base ledger holds {len(kb_events)} commands but the local "
            f"ledger holds {len(local_events)}; run the align-project-progress skill "
            "before archiving so the two histories are merged first"
        )
    if local_events[: len(kb_events)] != kb_events:
        shared = {
            event["command_id"] for event in kb_events
        } & {
            event["command_id"] for event in local_events
        }
        raise ArchiveError(
            "the knowledge base ledger diverges from the local ledger; refusing to "
            f"archive over {len(shared)} shared command(s). Compare the two ledger files."
        )
    return {
        "local_events": len(local_events),
        "kb_events": len(kb_events),
        "appended": len(local_events) - len(kb_events),
    }


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED_NAMES}


def copy_project_log(src: Path, dst: Path) -> dict:
    """Merge the local Project Log into the KB copy, ledger included, without deleting."""
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)
    ledger_source = src / LEDGER_RELATIVE
    if ledger_source.is_file():
        ledger_target = dst / LEDGER_RELATIVE
        ledger_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ledger_source, ledger_target)
    return {
        "files": sum(1 for item in dst.rglob("*") if item.is_file()),
        "ledger": str(dst / LEDGER_RELATIVE),
    }


def git_push(kb_root: Path, project_name: str) -> str:
    """Stage, commit, and push only this project's archive directory."""
    relative = str(Path("工程记录") / project_name)
    completed = subprocess.run(
        ["git", "-C", str(kb_root), "add", "-A", "--", relative],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        raise ArchiveError(f"git add failed: {completed.stderr.strip()}")
    staged = subprocess.run(
        ["git", "-C", str(kb_root), "diff", "--cached", "--quiet", "--", relative],
        check=False,
    )
    if staged.returncode == 0:
        return "no-changes"
    committed = subprocess.run(
        ["git", "-C", str(kb_root), "commit", "-m", f"archive: {project_name}"],
        capture_output=True, text=True, check=False,
    )
    if committed.returncode:
        raise ArchiveError(f"git commit failed: {committed.stderr.strip()}")
    pushed = subprocess.run(
        ["git", "-C", str(kb_root), "push"], capture_output=True, text=True, check=False,
    )
    if pushed.returncode:
        raise ArchiveError(f"git push failed: {pushed.stderr.strip()}")
    return "pushed"


def archive(project_root: Path, kb_base: Path) -> dict:
    root = Path(project_root).resolve()
    source = root / ".project-log"
    if not source.is_dir():
        raise ArchiveError(f".project-log not found in {root}")
    engineering = Path(kb_base).expanduser() / "工程记录"
    if not engineering.is_dir():
        raise ArchiveError(f"工程记录/ not found under {kb_base}")

    # The project name is the work folder name, exactly as the user specified.
    project_name = root.name
    destination = engineering / project_name / ".project-log"

    local_id = read_project_id(source)
    known_id = read_project_id(destination)
    if local_id and known_id and local_id != known_id:
        raise ArchiveError(
            f"project id mismatch for {project_name}: local {local_id} vs knowledge base "
            f"{known_id}; refusing to overwrite an unrelated project"
        )
    if local_id is None and (destination / LEDGER_RELATIVE).is_file():
        raise ArchiveError(
            f"{source / MARKER} has no project_id but the knowledge base already holds a "
            "ledger for this name; refusing to archive"
        )

    ledger = verify_ledger_superset(source / LEDGER_RELATIVE, destination / LEDGER_RELATIVE)
    copied = copy_project_log(source, destination)
    pushed = git_push(Path(kb_base).expanduser(), project_name)
    return {
        "project": project_name,
        "project_id": local_id,
        "destination": str(destination),
        "ledger": ledger,
        "files": copied["files"],
        "git": pushed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive project log to knowledge base")
    parser.add_argument("--project-root", required=True, help="Path to project root")
    parser.add_argument("--kb", help="Knowledge base root; defaults to the configured path")
    args = parser.parse_args()
    try:
        kb_base = Path(args.kb) if args.kb else get_kb_base()
        report = archive(Path(args.project_root), kb_base)
    except ArchiveError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
