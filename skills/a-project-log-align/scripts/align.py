#!/usr/bin/env python3
"""Merge an archived .project-log from the knowledge base into the current work folder.

The knowledge base copy is the transport, the local ledger is the workspace. Aligning
unions the two ledgers by ``command_id`` so no command is ever dropped, re-seals the
hash chain, and then replays the merged ledger into the local SQLite projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "scripts" / "kb_path.conf"
ARCHIVE_CONFIG = (
    SKILL_DIR.parent / "a-project-log-archive" / "scripts" / "kb_path.conf"
)
PLACEHOLDER = "__UNSET__"
LEDGER_RELATIVE = Path("ledger") / "v1" / "ledger.jsonl"
MARKER = "state-format.json"
LEDGER_SCHEMA_VERSION = 1
GENESIS_HASH = ""
EVENT_FIELDS = (
    "schema_version", "command_id", "origin_kind", "origin_context_id",
    "origin_revision", "action", "request", "request_hash", "receipt",
    "created_at", "previous_hash",
)


class AlignError(RuntimeError):
    """A condition the operator must resolve before aligning can continue."""


def _configured_path(path: Path) -> str | None:
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw or raw == PLACEHOLDER:
        return None
    return raw


def resolve_kb_base(explicit: str | None) -> Path:
    """Resolve the knowledge base root from the flag, skill configs or the environment."""
    for candidate in (
        explicit,
        _configured_path(CONFIG),
        _configured_path(ARCHIVE_CONFIG),
        os.environ.get("VIBE_KB_PATH"),
    ):
        if candidate:
            return Path(candidate).expanduser()
    raise AlignError(
        "knowledge base path is unconfigured; pass --kb, set VIBE_KB_PATH, or configure "
        f"{CONFIG} (the a-project-log-archive skill writes the same setting)"
    )


def _canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


def read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise AlignError(f"cannot read ledger {path}: {error}") from error
    events: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise AlignError(f"{path}:{number} is not valid JSON: {error}") from error
        if type(event) is not dict or set(event) != set(EVENT_FIELDS) | {"event_hash"}:
            raise AlignError(f"{path}:{number} is not a supported ledger event")
        if event["schema_version"] != LEDGER_SCHEMA_VERSION:
            raise AlignError(f"{path}:{number} has an unsupported schema_version")
        events.append(event)
    return events


def _seal(body: dict) -> dict:
    digest = hashlib.sha256(
        (body["previous_hash"] + "\n" + _canonical(body)).encode("utf-8")
    ).hexdigest()
    return {**body, "event_hash": digest}


def render_ledger(events: list[dict]) -> str:
    """Re-seal a merged event list into canonical JSONL, preserving each body."""
    lines = []
    previous = GENESIS_HASH
    for event in events:
        body = {key: event[key] for key in EVENT_FIELDS}
        body["previous_hash"] = previous
        sealed = _seal(body)
        previous = sealed["event_hash"]
        lines.append(_canonical(sealed))
    return "".join(line + "\n" for line in lines)


def merge_ledgers(archived: list[dict], local: list[dict]) -> tuple[list[dict], dict]:
    """Union two ledgers by command_id, keeping archived order then local-only tail."""
    archived_ids = {event["command_id"] for event in archived}
    local_by_id = {event["command_id"]: event for event in local}
    for event in archived:
        known = local_by_id.get(event["command_id"])
        if known is not None and _canonical(known) != _canonical(event):
            raise AlignError(
                f"command {event['command_id']} differs between the archive and the local "
                "ledger; refusing to merge conflicting history"
            )
    merged = list(archived)
    appended = [event for event in local if event["command_id"] not in archived_ids]
    merged.extend(appended)
    local_ids = set(local_by_id)
    return merged, {
        "archived_events": len(archived),
        "local_events": len(local),
        "adopted_from_archive": len(archived_ids - local_ids),
        "kept_local_only": len(appended),
        "merged_events": len(merged),
    }


def read_project_id(log: Path) -> str | None:
    marker = log / MARKER
    if not marker.is_file():
        return None
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AlignError(f"{marker} is not readable JSON: {error}") from error
    if type(document) is not dict:
        raise AlignError(f"{marker} is not a JSON object")
    identifier = document.get("project_id")
    if identifier is not None and type(identifier) is not str:
        raise AlignError(f"{marker} has a non-string project_id")
    return identifier


def merge_docs(archived_log: Path, local_log: Path) -> dict:
    """Copy archived docs that are missing locally; never overwrite a local doc."""
    source = archived_log / "docs"
    if not source.is_dir():
        return {"copied": [], "conflicts": []}
    copied: list[str] = []
    conflicts: list[str] = []
    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        target = local_log / "docs" / relative
        if target.exists():
            if target.read_bytes() != item.read_bytes():
                conflicts.append(relative.as_posix())
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, target)
        copied.append(relative.as_posix())
    return {"copied": copied, "conflicts": conflicts}


def _python_executable() -> str:
    override = os.environ.get("VIBE_PYTHON")
    if override:
        return override
    config_root = Path(
        os.environ.get("OPENCODE_CONFIG_DIR")
        or (Path.home() / ".config" / "opencode")
    )
    configured = config_root / "vibe-python"
    if configured.is_file():
        value = configured.read_text(encoding="utf-8").strip()
        if value:
            return value
    return sys.executable


def _vibe_runtime() -> Path:
    configured = os.environ.get("VIBE_RUNTIME")
    if configured:
        return Path(configured).expanduser()
    config_root = Path(
        os.environ.get("OPENCODE_CONFIG_DIR")
        or (Path.home() / ".config" / "opencode")
    )
    return config_root / "vibe-workflow"


def run_vibe(root: Path, *arguments: str) -> dict:
    """Run the formal vibe command surface against the work folder."""
    runtime = _vibe_runtime()
    script = runtime / "scripts" / "vibe.py"
    if not script.is_file():
        raise AlignError(
            f"vibe runtime not found at {script}; set VIBE_RUNTIME or run "
            "'vibe state-attach' manually after aligning"
        )
    completed = subprocess.run(
        [_python_executable(), str(script), "--root", str(root), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise AlignError(f"vibe {' '.join(arguments)} failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except ValueError:
        return {"stdout": completed.stdout.strip()}


def align(project_root: Path, kb_base: Path, attach: bool = True, dry_run: bool = False) -> dict:
    root = Path(project_root).resolve()
    local_log = root / ".project-log"
    if not local_log.is_dir():
        raise AlignError(f".project-log not found in {root}; run 'vibe init' first")
    project_name = root.name
    archived_log = Path(kb_base).expanduser() / "工程记录" / project_name / ".project-log"
    if not archived_log.is_dir():
        raise AlignError(
            f"no archived Project Log for {project_name!r} under "
            f"{Path(kb_base).expanduser() / '工程记录'}; archive this project first"
        )

    local_id = read_project_id(local_log)
    archived_id = read_project_id(archived_log)
    if local_id and archived_id and local_id != archived_id:
        raise AlignError(
            f"project id mismatch for {project_name}: local {local_id} vs archive "
            f"{archived_id}; refusing to merge unrelated projects"
        )

    merged, ledger_report = merge_ledgers(
        read_ledger(archived_log / LEDGER_RELATIVE),
        read_ledger(local_log / LEDGER_RELATIVE),
    )
    docs_report = {"copied": [], "conflicts": []}
    if not dry_run:
        target = local_log / LEDGER_RELATIVE
        target.parent.mkdir(parents=True, exist_ok=True)
        text = render_ledger(merged)
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_text(text, encoding="utf-8", newline="\n")
            os.replace(temporary, target)
        if archived_id and not local_id:
            (local_log / MARKER).write_text(
                _canonical({"format": 2, "project_id": archived_id}) + "\n",
                encoding="utf-8",
            )
        docs_report = merge_docs(archived_log, local_log)

    report = {
        "project": project_name,
        "project_id": local_id or archived_id,
        "archive": str(archived_log),
        "dry_run": dry_run,
        "ledger": ledger_report,
        "docs": docs_report,
        "attach": None,
        "validate": None,
    }
    if not dry_run and attach:
        report["attach"] = run_vibe(root, "state-attach")
        report["validate"] = run_vibe(root, "validate")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Align project logs from the knowledge base")
    parser.add_argument("--project-root", required=True, help="Path to the work folder")
    parser.add_argument("--kb", help="Knowledge base root; defaults to the configured path")
    parser.add_argument("--dry-run", action="store_true", help="Preview the merge only")
    parser.add_argument("--no-attach", action="store_true", help="Skip the SQLite rebuild")
    args = parser.parse_args()
    try:
        report = align(
            Path(args.project_root), resolve_kb_base(args.kb),
            attach=not args.no_attach, dry_run=args.dry_run,
        )
    except AlignError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
