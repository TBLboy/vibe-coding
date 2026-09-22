"""Format 3 ledger: an append-only, Git-tracked, single linear event stream.

The ledger is the durable fact source for a project; the SQLite store is a
projection that can be deleted and rebuilt by replaying it. Every event carries
the full command record needed to reproduce the row byte-for-byte: command
identity, origin metadata, canonical request, request hash, receipt and
timestamp. ``state_replay.reduce_ledger`` turns that stream back into entities.

The ledger is deliberately a single ordered file rather than per-writer streams:
this framework serves one user on one machine at a time, so a linear append is
the whole conflict model. Merging across machines dedupes by the globally unique
``command_id`` and appends in arrival order.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from state_replay import logical_state_hash, reduce_ledger
from state_store import StateError, _json


LEDGER_SCHEMA_VERSION = 1
LEDGER_RELATIVE = Path(".project-log") / "ledger" / "v1" / "ledger.jsonl"
GENESIS_HASH = ""
EVENT_FIELDS = (
    "schema_version", "command_id", "origin_kind", "origin_context_id",
    "origin_revision", "action", "request", "request_hash", "receipt",
    "created_at", "previous_hash", "event_hash",
)


def ledger_path(root: Path) -> Path:
    return Path(root).resolve() / LEDGER_RELATIVE


def _event_body(row: dict, previous_hash: str) -> dict:
    """Build one ledger event body, proving the structured form is byte-lossless."""
    try:
        request = json.loads(row["request_json"])
        receipt = json.loads(row["receipt_json"])
    except (TypeError, ValueError) as error:
        raise StateError(
            "invalid_ledger", f"Command {row['command_id']} is not valid JSON: {error}"
        ) from error
    if _json(request) != row["request_json"]:
        raise StateError("invalid_ledger", f"Command {row['command_id']} request is not canonical")
    if _json(receipt) != row["receipt_json"]:
        raise StateError("invalid_ledger", f"Command {row['command_id']} receipt is not canonical")
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "command_id": row["command_id"],
        "origin_kind": row["origin_kind"],
        "origin_context_id": row["origin_context_id"],
        "origin_revision": row["origin_revision"],
        "action": row["action"],
        "request": request,
        "request_hash": row["request_hash"],
        "receipt": receipt,
        "created_at": row["created_at"],
        "previous_hash": previous_hash,
    }


def _seal(body: dict) -> dict:
    """Append the hash that chains this event to the one before it."""
    digest = hashlib.sha256(
        (body["previous_hash"] + "\n" + _json(body)).encode("utf-8")
    ).hexdigest()
    sealed = dict(body)
    sealed["event_hash"] = digest
    return sealed


def _verify_seal(event: dict) -> None:
    body = {key: event[key] for key in event if key != "event_hash"}
    digest = hashlib.sha256(
        (body["previous_hash"] + "\n" + _json(body)).encode("utf-8")
    ).hexdigest()
    if digest != event.get("event_hash"):
        raise StateError(
            "invalid_ledger", f"Ledger event {event.get('command_id')} failed its hash chain check"
        )


def render_ledger(rows) -> str:
    """Serialize ordered command rows into canonical JSONL ledger text."""
    lines = []
    previous_hash = GENESIS_HASH
    for index, row in enumerate(rows, start=1):
        if row["local_sequence"] != index:
            raise StateError(
                "invalid_ledger",
                "Command sequences are not contiguous; refusing to export a lossy ledger",
            )
        event = _seal(_event_body(row, previous_hash))
        previous_hash = event["event_hash"]
        lines.append(_json(event))
    return "".join(line + "\n" for line in lines)


def read_ledger(path: Path) -> list[dict]:
    """Parse a ledger file into ``commands``-shaped rows for replay."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise StateError("invalid_ledger", f"Cannot read ledger: {error}") from error
    entries: list[dict] = []
    previous_hash = GENESIS_HASH
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise StateError(
                "invalid_ledger", f"Ledger line {number} is not valid JSON: {error}"
            ) from error
        if type(event) is not dict or set(event) != set(EVENT_FIELDS):
            raise StateError("invalid_ledger", f"Ledger line {number} has unsupported fields")
        if event["schema_version"] != LEDGER_SCHEMA_VERSION:
            raise StateError("invalid_ledger", f"Ledger line {number} has an unsupported schema")
        if event["previous_hash"] != previous_hash:
            raise StateError("invalid_ledger", f"Ledger line {number} breaks the hash chain")
        _verify_seal(event)
        previous_hash = event["event_hash"]
        entries.append({
            "local_sequence": len(entries) + 1,
            "command_id": event["command_id"],
            "origin_kind": event["origin_kind"],
            "origin_context_id": event["origin_context_id"],
            "origin_revision": event["origin_revision"],
            "action": event["action"],
            "request_json": _json(event["request"]),
            "request_hash": event["request_hash"],
            "receipt_json": _json(event["receipt"]),
            "created_at": event["created_at"],
        })
    return entries


def _command_rows(store) -> list[dict]:
    with store._connection() as connection:
        connection.execute("BEGIN")
        return [
            {key: row[key] for key in row.keys()}
            for row in connection.execute("SELECT * FROM commands ORDER BY local_sequence")
        ]


def export_ledger(store, path: Path | None = None) -> dict:
    """Write every accepted command to the Git-tracked ledger, idempotently."""
    if path is None:
        if store.root is None:
            raise StateError("invalid_root", "Cannot locate the ledger without a project root")
        path = ledger_path(store.root)
    path = Path(path)
    rows = _command_rows(store)
    text = render_ledger(rows)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    unchanged = existing == text
    if not unchanged:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    return {
        "path": str(path),
        "events": len(rows),
        "revision": rows[-1]["local_sequence"] if rows else 0,
        "sha256": digest,
        "unchanged": unchanged,
    }


def verify_ledger(root: Path, store=None) -> dict:
    """Replay the ledger file and compare it table-by-table with the live store."""
    if store is None:
        from state_context import open_store

        store = open_store(root)
    path = ledger_path(root)
    entries = read_ledger(path)
    reduced = reduce_ledger(entries)
    with store._connection() as connection:
        live = store._entity_rows(connection)
    mismatches = [table for table in reduced if reduced[table] != live[table]]
    return {
        "path": str(path),
        "events": len(entries),
        "revision": store.status()["revision"],
        "logical_state_hash": logical_state_hash(reduced),
        "matches": not mismatches,
        "mismatches": mismatches,
    }


def _last_line(path: Path) -> str | None:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        position = stream.tell()
        buffer = b""
        while position > 0:
            step = min(4096, position)
            position -= step
            stream.seek(position)
            buffer = stream.read(step) + buffer
            stripped = buffer.rstrip(b"\r\n")
            if b"\n" in stripped:
                return stripped.rsplit(b"\n", 1)[-1].decode("utf-8")
        return buffer.strip().decode("utf-8") or None


def ledger_tip(path: Path) -> dict | None:
    """Read only the final ledger event, so freshness checks stay O(1)."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        line = _last_line(path)
    except (OSError, UnicodeError) as error:
        raise StateError("invalid_ledger", f"Cannot read the ledger tip: {error}") from error
    if line is None:
        return None
    try:
        return json.loads(line)
    except ValueError as error:
        raise StateError("invalid_ledger", f"The ledger tip is not valid JSON: {error}") from error


def ledger_freshness(root: Path, revision: int) -> dict:
    """Cheap check of whether the ledger's last event is the store's revision."""
    path = ledger_path(root)
    tip = ledger_tip(path)
    tip_revision = tip["origin_revision"] if tip else 0
    return {
        "ledger_present": path.is_file(),
        "ledger_tip_revision": tip_revision,
        "store_revision": revision,
        "unexported_commands": max(0, revision - tip_revision),
        "in_sync": revision == tip_revision,
    }


def _git(root: Path, *arguments: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return completed.returncode == 0, completed.stdout.strip()


def portability_status(root: Path) -> dict:
    """Report whether local history is durably captured by the Git-tracked ledger.

    "Tracked by Git" is not the same as "safe": the ledger can be stale (the store
    holds commands it never exported), modified but uncommitted, or committed but
    unpushed. This reports each of those so a finishing session can refuse to call
    the work portable while history is still only on this machine.
    """
    root = Path(root).resolve()
    path = ledger_path(root)
    entries = read_ledger(path)
    try:
        from state_context import open_store

        revision = open_store(root).status()["revision"]
    except StateError:
        revision = None
    unexported = max(0, revision - len(entries)) if revision is not None else None
    report = {
        "ledger_path": str(path),
        "ledger_present": path.is_file(),
        "ledger_events": len(entries),
        "store_revision": revision,
        "unexported_commands": unexported,
        "in_sync": unexported == 0,
        "git": None,
    }
    inside, _ = _git(root, "rev-parse", "--show-toplevel")
    if inside:
        relative = path.relative_to(root).as_posix()
        tracked, _ = _git(root, "ls-files", "--error-unmatch", "--", relative)
        _, changes = _git(root, "status", "--porcelain", "--", relative)
        known, ahead = _git(root, "rev-list", "--count", "@{upstream}..HEAD")
        report["git"] = {
            "ledger_tracked": tracked,
            "uncommitted_ledger_changes": bool(changes),
            "upstream_known": known,
            "unpushed_commits": int(ahead) if known and ahead.isdigit() else 0,
        }
        report["portable"] = bool(
            report["in_sync"] and tracked and not changes and known
            and report["git"]["unpushed_commits"] == 0
        )
    else:
        # A plain work directory carries no remote of its own; the KB is the
        # transport, so the only signal available here is ledger freshness.
        report["portable"] = report["in_sync"]
    return report
