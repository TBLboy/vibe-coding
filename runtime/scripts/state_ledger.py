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


def _tail_lines(path: Path, count: int) -> list[str]:
    """Return up to ``count`` trailing non-empty lines without reading the whole file."""
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        position = stream.tell()
        buffer = b""
        while position > 0:
            step = min(65536, position)
            position -= step
            stream.seek(position)
            buffer = stream.read(step) + buffer
            if buffer.count(b"\n") > count:
                break
    parts = buffer.split(b"\n")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    try:
        return [part.decode("utf-8") for part in parts[-count:] if part]
    except UnicodeError as error:
        raise StateError("invalid_ledger", f"Cannot decode the ledger tail: {error}") from error


def _ensure_append_ready(path: Path) -> None:
    """Drop an incomplete trailing write so the next append starts on a clean line.

    A process killed mid-``write`` can leave a partial final line. Because the
    ledger append is the commit point and it always precedes the SQLite commit, an
    incomplete tail can only belong to a command that was never committed, so it is
    safe to truncate. A tail that is already a complete event but merely lacks the
    trailing newline is completed instead of dropped.
    """
    if not path.is_file():
        return
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        if size == 0:
            return
        stream.seek(size - 1)
        if stream.read(1) == b"\n":
            # The ledger already ends on a line boundary; nothing to repair.
            return
    lines = _tail_lines(path, 1)
    if not lines:
        return
    tail = lines[-1].encode("utf-8")
    try:
        event = json.loads(tail.decode("utf-8"))
        complete = type(event) is dict and set(event) == set(EVENT_FIELDS)
    except (ValueError, UnicodeError):
        complete = False
    with path.open("r+b") as stream:
        if complete:
            stream.seek(0, os.SEEK_END)
            stream.write(b"\n")
        else:
            stream.seek(0, os.SEEK_END)
            position = stream.tell()
            buffer = b""
            while position > 0 and b"\n" not in buffer:
                step = min(65536, position)
                position -= step
                stream.seek(position)
                buffer = stream.read(step) + buffer
            if b"\n" not in buffer:
                stream.truncate(0)
            else:
                stream.truncate(position + buffer.rfind(b"\n") + 1)
        stream.flush()
        os.fsync(stream.fileno())


def append_event(
    path: Path,
    *,
    command_id: str,
    origin_kind: str,
    origin_context_id: str,
    origin_revision: int,
    action: str,
    request: dict,
    request_hash: str,
    receipt: dict,
    created_at: str,
) -> dict:
    """Append one sealed event to the ledger and fsync it: the durable commit point.

    This is the write path the store uses before it updates SQLite, so a crash
    between the two leaves a ledger that is ahead of the projection. Replaying the
    ledger (``state-attach``) then restores the missing command.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_append_ready(path)
    previous_hash = GENESIS_HASH
    if path.is_file():
        tip = ledger_tip(path)
        if tip is not None:
            _verify_seal(tip)
            previous_hash = tip["event_hash"]
    body = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "command_id": command_id,
        "origin_kind": origin_kind,
        "origin_context_id": origin_context_id,
        "origin_revision": origin_revision,
        "action": action,
        "request": request,
        "request_hash": request_hash,
        "receipt": receipt,
        "created_at": created_at,
        "previous_hash": previous_hash,
    }
    sealed = _seal(body)
    line = (_json(sealed) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        written = os.write(descriptor, line)
        if written != len(line):
            os.ftruncate(descriptor, path.stat().st_size - written)
            raise StateError("ledger_io", "Short write to the ledger; retry the command")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return sealed


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


def ledger_tip(path: Path) -> dict | None:
    """Read only the final complete ledger event, so freshness checks stay O(1).

    A process killed mid-append can leave a partial trailing line. That line never
    became a committed command, so it is skipped and the tip is the last line that
    parses as a complete event. ``read_ledger`` stays strict and reports it.
    """
    path = Path(path)
    if not path.is_file():
        return None
    try:
        lines = _tail_lines(path, 2)
    except OSError as error:
        raise StateError("invalid_ledger", f"Cannot read the ledger tip: {error}") from error
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if type(event) is dict and set(event) == set(EVENT_FIELDS):
            return event
    return None


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
