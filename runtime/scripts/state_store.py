from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote


SCHEMA_VERSION = 1
STORE_SCHEMA = 2
MAX_LIMIT = 100
MAX_REQUEST_BYTES = 65536
MAX_REVISION = 9223372036854775806
BUSY_TIMEOUT_MS = 5000


class StateError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def native_path(path: Path) -> Path:
    """Normalize Windows paths before opting into extended-length filesystem APIs."""
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt":
        return Path(absolute)
    absolute = os.path.normpath(absolute)
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _text(value, name: str, maximum: int = 8192) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise StateError("invalid_input", f"{name} must be nonempty text, at most {maximum} characters")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise StateError("invalid_input", f"{name} contains control characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise StateError("invalid_input", f"{name} is not valid Unicode") from error
    return value


def _integer(value, name: str, maximum: int = MAX_REVISION) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise StateError("invalid_input", f"{name} must be an integer between 0 and {maximum}")
    return value


def _limit(value: int) -> int:
    _integer(value, "limit", MAX_LIMIT)
    if value == 0:
        raise StateError("invalid_input", "limit must be positive")
    return value


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_tree(value, depth: int = 0, budget=None) -> None:
    if budget is None:
        budget = [4096, MAX_REQUEST_BYTES]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise StateError("invalid_input", "JSON nesting or element limit exceeded")
    if type(value) is str:
        try:
            budget[1] -= len(value.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise StateError("invalid_input", "JSON contains invalid Unicode") from error
        if budget[1] < 0:
            raise StateError("invalid_input", "JSON text size limit exceeded")
    elif type(value) is dict:
        if len(value) > 4096:
            raise StateError("invalid_input", "JSON object too large")
        for key, child in value.items():
            if type(key) is not str:
                raise StateError("invalid_input", "JSON keys must be strings")
            _json_tree(key, depth + 1, budget)
            _json_tree(child, depth + 1, budget)
    elif type(value) is list:
        if len(value) > 4096:
            raise StateError("invalid_input", "JSON array too large")
        for child in value:
            _json_tree(child, depth + 1, budget)
    elif type(value) is float:
        if not math.isfinite(value):
            raise StateError("invalid_input", "JSON numbers must be finite")
    elif type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise StateError("invalid_input", "JSON integer outside signed 64-bit range")
    elif value is not None and type(value) is not bool:
        raise StateError("invalid_input", "Only JSON values are supported")


def _request(envelope: dict) -> tuple[dict, str, str]:
    fields = {"schema_version", "command_id", "expected_revision", "action", "payload"}
    if type(envelope) is not dict or set(envelope) != fields:
        raise StateError("invalid_input", "Operation envelope has missing or unknown fields")
    _integer(envelope["schema_version"], "schema_version", 1)
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise StateError("invalid_input", "Unsupported schema_version")
    _integer(envelope["expected_revision"], "expected_revision")
    _text(envelope["command_id"], "command_id", 256)
    action = _text(envelope["action"], "action", 64)
    shapes = {
        "goal.create": ({"id", "title"}, {"extensions"}),
        "task.create": ({"id", "title", "goal_id"}, {"extensions"}),
        "task.begin": ({"task_id", "run_id", "next_action"}, set()),
        "task.wait": ({"task_id", "kind", "reason", "resume_when"}, {"question_ref"}),
        "task.resume": ({"task_id", "next_action"}, set()),
        "task.handoff": ({"task_id", "next_action"}, set()),
        "task.finish": ({"task_id", "summary"}, set()),
        "task.cancel": ({"task_id", "reason"}, set()),
    }
    if action not in shapes:
        raise StateError("unsupported_action", f"Unsupported action: {action}")
    payload = envelope["payload"]
    required, optional = shapes[action]
    if type(payload) is not dict or not required <= set(payload) or set(payload) - required - optional:
        raise StateError("invalid_input", f"{action} payload has missing or unknown fields")
    for key, value in payload.items():
        if key == "extensions":
            if type(value) is not dict:
                raise StateError("invalid_input", "extensions must be an object")
        elif key == "goal_id" and value is None:
            continue
        else:
            maximum = 256 if key in {"id", "task_id", "run_id", "goal_id", "question_ref"} else 8192
            _text(value, key, maximum)
    if action == "task.wait":
        if payload["kind"] not in {"user", "dependency", "environment"}:
            raise StateError("invalid_input", "Unknown wait kind")
        if (payload["kind"] == "user") != ("question_ref" in payload):
            raise StateError("invalid_input", "question_ref is required only for user waits")
    _json_tree(envelope)
    canonical = _json(envelope)
    encoded = canonical.encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise StateError("invalid_input", "Operation exceeds 65536 encoded bytes")
    return json.loads(canonical), canonical, hashlib.sha256(encoded).hexdigest()


# `origin_kind` records how the *originating* repository obtained a command
# ('local' when minted there, 'imported' when it had received it), so the value
# is stable across clones and can be compared byte-for-byte during import.
_BUNDLE_COLUMNS = {
    "goals": ("id", "title", "status", "extensions", "created_sequence", "updated_sequence"),
    "tasks": ("id", "title", "goal_id", "status", "run_id", "next_action", "summary",
              "cancel_reason", "extensions", "created_sequence", "updated_sequence"),
    "runs": ("id", "task_id", "status", "created_sequence", "updated_sequence"),
    "blockers": ("id", "task_id", "run_id", "kind", "reason", "question_ref", "resume_when",
                 "created_sequence", "resolved_sequence"),
    "ledger": ("local_sequence", "command_id", "origin_kind", "origin_context_id", "origin_revision",
               "action", "request_json", "request_hash", "receipt_json", "created_at"),
}
_BUNDLE_FIELDS = {"schema_version", "project_id", "context_id", "local_revision", "base_snapshot"} | set(_BUNDLE_COLUMNS)
_BUNDLE_INTEGERS = {"local_sequence", "origin_revision", "created_sequence", "updated_sequence", "resolved_sequence"}


def _validate_bundle(bundle) -> dict:
    """Shape-check a portable snapshot payload before any semantic comparison."""
    if type(bundle) is not dict or set(bundle) != _BUNDLE_FIELDS:
        raise StateError("invalid_snapshot", "Snapshot payload has missing or unknown fields")
    if type(bundle["schema_version"]) is not int or bundle["schema_version"] != SCHEMA_VERSION:
        raise StateError("invalid_snapshot", "Unsupported snapshot schema version")
    _text(bundle["project_id"], "project_id", 256)
    _text(bundle["context_id"], "context_id", 256)
    _integer(bundle["local_revision"], "local_revision")
    if bundle["base_snapshot"] is not None:
        _text(bundle["base_snapshot"], "base_snapshot", 64)
    for name, columns in _BUNDLE_COLUMNS.items():
        rows = bundle[name]
        if type(rows) is not list or len(rows) > MAX_LIMIT * 1000:
            raise StateError("invalid_snapshot", f"{name} must be a bounded list")
        for row in rows:
            if type(row) is not dict or set(row) != set(columns):
                raise StateError("invalid_snapshot", f"{name} entry has missing or unknown fields")
            for key, value in row.items():
                if value is None:
                    continue
                if key in _BUNDLE_INTEGERS or (key == "id" and type(value) is int):
                    _integer(value, f"{name}.{key}")
                    continue
                _text(value, f"{name}.{key}", MAX_REQUEST_BYTES)
    ledger = bundle["ledger"]
    if [row["local_sequence"] for row in ledger] != list(range(1, len(ledger) + 1)):
        raise StateError("invalid_snapshot", "Snapshot ledger is not a contiguous local sequence")
    if bundle["local_revision"] != len(ledger):
        raise StateError("invalid_snapshot", "Snapshot local revision disagrees with its ledger")
    if len({row["command_id"] for row in ledger}) != len(ledger):
        raise StateError("invalid_snapshot", "Snapshot ledger repeats a command identity")
    return bundle


_DDL = (
    """CREATE TABLE metadata (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        store_schema INTEGER NOT NULL CHECK(store_schema = 2),
        schema_version INTEGER NOT NULL CHECK(schema_version = 1),
        project_id TEXT NOT NULL, context_id TEXT NOT NULL,
        local_revision INTEGER NOT NULL CHECK(local_revision >= 0))""",
    """CREATE TABLE goals (
        id TEXT PRIMARY KEY, title TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status = 'active'), extensions TEXT NOT NULL,
        created_sequence INTEGER NOT NULL, updated_sequence INTEGER NOT NULL)""",
    """CREATE TABLE tasks (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, goal_id TEXT REFERENCES goals(id),
        status TEXT NOT NULL CHECK(status IN ('ready','in-progress','waiting-user','blocked',
            'handed-off','implemented-unverified','cancelled')),
        run_id TEXT UNIQUE REFERENCES runs(id), next_action TEXT,
        summary TEXT, cancel_reason TEXT, extensions TEXT NOT NULL,
        created_sequence INTEGER NOT NULL, updated_sequence INTEGER NOT NULL)""",
    """CREATE TABLE runs (
        id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
        status TEXT NOT NULL CHECK(status IN ('active','waiting-user','blocked','handed-off','finished','cancelled')),
        created_sequence INTEGER NOT NULL, updated_sequence INTEGER NOT NULL)""",
    "CREATE UNIQUE INDEX one_active_run ON runs(status) WHERE status = 'active'",
    "CREATE INDEX recent_tasks ON tasks(updated_sequence DESC, id)",
    "CREATE INDEX tasks_goal ON tasks(goal_id)",
    """CREATE TABLE blockers (
        id INTEGER PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
        run_id TEXT NOT NULL REFERENCES runs(id),
        kind TEXT NOT NULL CHECK(kind IN ('user','dependency','environment')),
        reason TEXT NOT NULL, question_ref TEXT, resume_when TEXT NOT NULL,
        created_sequence INTEGER NOT NULL, resolved_sequence INTEGER,
        CHECK((kind = 'user' AND question_ref IS NOT NULL) OR
            (kind != 'user' AND question_ref IS NULL)))""",
    "CREATE UNIQUE INDEX one_open_blocker ON blockers(task_id) WHERE resolved_sequence IS NULL",
    "CREATE INDEX blockers_run ON blockers(run_id)",
    """CREATE TABLE commands (
        command_id TEXT PRIMARY KEY, local_sequence INTEGER NOT NULL UNIQUE,
        origin_kind TEXT NOT NULL CHECK(origin_kind IN ('local','imported')),
        origin_context_id TEXT NOT NULL, origin_revision INTEGER NOT NULL,
        action TEXT NOT NULL, request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
        receipt_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE events (
        local_sequence INTEGER PRIMARY KEY REFERENCES commands(local_sequence),
        command_id TEXT NOT NULL UNIQUE REFERENCES commands(command_id),
        origin_kind TEXT NOT NULL CHECK(origin_kind IN ('local','imported')),
        origin_context_id TEXT NOT NULL, origin_revision INTEGER NOT NULL,
        action TEXT NOT NULL, request_hash TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE projection_jobs (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1), local_revision INTEGER NOT NULL CHECK(local_revision >= 0))""",
    """CREATE TABLE exchange (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        base_snapshot TEXT CHECK(base_snapshot IS NULL OR length(base_snapshot) = 64),
        exported_local_revision INTEGER NOT NULL CHECK(exported_local_revision >= 0),
        pending_kind TEXT CHECK(pending_kind IS NULL OR pending_kind IN ('export','import')),
        pending_snapshot TEXT CHECK(pending_snapshot IS NULL OR length(pending_snapshot) = 64),
        pending_base TEXT CHECK(pending_base IS NULL OR length(pending_base) = 64),
        pending_revision INTEGER,
        CHECK((pending_kind IS NULL) = (pending_snapshot IS NULL)),
        CHECK((pending_kind IS NULL) = (pending_revision IS NULL)))""",
)


class Store:
    """One explicitly initialized database bound to one project and branch context."""

    def __init__(self, path: Path, project_id: str, context_id: str):
        self.path = native_path(path)
        self.project_id = _text(project_id, "project_id", 256)
        self.context_id = _text(context_id, "context_id", 256)

    @contextmanager
    def _connection(self, write: bool = False):
        if not self.path.is_file():
            raise StateError("missing_store", f"State database does not exist: {self.path}")
        connection = None
        try:
            mode = "rw" if write else "ro"
            uri = "file:" + quote(str(self.path), safe="/:") if os.name == "nt" else self.path.as_uri()
            connection = sqlite3.connect(
                uri + f"?mode={mode}", uri=True,
                timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            if not write:
                connection.execute("PRAGMA query_only = ON")
            yield connection
        except sqlite3.Error as error:
            code = getattr(error, "sqlite_errorcode", 0) & 255
            if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise StateError("busy_writer", "State database is busy; retry the same command") from error
            raise StateError("state_conflict", f"State database error: {error}") from error
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    def _metadata(self, connection) -> dict:
        row = connection.execute("SELECT * FROM metadata WHERE singleton = 1").fetchone()
        if row is None or row["store_schema"] != STORE_SCHEMA or row["schema_version"] != SCHEMA_VERSION:
            raise StateError("state_conflict", "Missing or unsupported store metadata")
        if row["project_id"] != self.project_id or row["context_id"] != self.context_id:
            raise StateError("context_mismatch", "Store project/context binding does not match")
        return dict(row)

    def initialize(self) -> dict:
        """Reserve a new file exclusively; interrupted initialization is never overwritten."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise StateError("store_exists", f"Refusing to overwrite: {self.path}") from error
        except OSError as error:
            raise StateError("store_io", str(error)) from error
        os.close(descriptor)
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for statement in _DDL:
                connection.execute(statement)
            connection.execute("INSERT INTO metadata VALUES (1, ?, ?, ?, ?, 0)",
                               (STORE_SCHEMA, SCHEMA_VERSION, self.project_id, self.context_id))
            connection.execute("INSERT INTO projection_jobs VALUES (1, 0)")
            connection.execute("INSERT INTO exchange VALUES (1, NULL, 0, NULL, NULL, NULL, NULL)")
            connection.commit()
        return self.status()

    @staticmethod
    def _task(connection, task_id: str) -> dict:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise StateError("not_found", f"Unknown task: {task_id}")
        task = dict(row)
        task["extensions"] = json.loads(task["extensions"])
        run = connection.execute("SELECT * FROM runs WHERE id = ?", (task["run_id"],)).fetchone()
        blocker = connection.execute(
            "SELECT * FROM blockers WHERE task_id = ? AND resolved_sequence IS NULL", (task_id,)
        ).fetchone()
        task["run"] = dict(run) if run else None
        task["blocker"] = dict(blocker) if blocker else None
        return task

    def get_task(self, task_id: str) -> dict:
        _text(task_id, "task_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            return self._task(connection, task_id)

    @staticmethod
    def _history(connection, limit: int) -> list[dict]:
        return [
            {"local_sequence": row["local_sequence"], "receipt": json.loads(row["receipt_json"])}
            for row in connection.execute(
                "SELECT local_sequence, receipt_json FROM commands ORDER BY local_sequence DESC LIMIT ?",
                (limit,),
            )
        ]

    def history(self, limit: int = 20) -> list[dict]:
        _limit(limit)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            return self._history(connection, limit)

    def _snapshot(self, connection, limit: int) -> dict:
        metadata = self._metadata(connection)
        active = connection.execute("SELECT * FROM runs WHERE status = 'active'").fetchone()
        pending = connection.execute("SELECT local_revision FROM projection_jobs WHERE singleton = 1").fetchone()
        task_ids = connection.execute(
            "SELECT id FROM tasks ORDER BY updated_sequence DESC, id LIMIT ?", (limit,)
        ).fetchall()
        return {
            "schema_version": SCHEMA_VERSION, "project_id": metadata["project_id"],
            "store_schema": metadata["store_schema"], "context_id": metadata["context_id"],
            "revision": metadata["local_revision"], "local_revision": metadata["local_revision"],
            "current_run": dict(active) if active else None,
            "current_task": self._task(connection, active["task_id"]) if active else None,
            "tasks": [self._task(connection, row["id"]) for row in task_ids],
            "projection_pending": pending is not None,
            "projection_revision": pending["local_revision"] if pending else None,
        }

    def status(self, limit: int = 10) -> dict:
        _limit(limit)
        with self._connection() as connection:
            connection.execute("BEGIN")
            return self._snapshot(connection, limit)

    def view_snapshot(self, limit: int = 10) -> dict:
        """Bounded state and receipts from one explicit, coherent read transaction."""
        _limit(limit)
        with self._connection() as connection:
            connection.execute("BEGIN")
            snapshot = self._snapshot(connection, limit)
            snapshot["history"] = self._history(connection, limit)
            return snapshot

    @staticmethod
    def _active_goal(connection, goal_id) -> None:
        if goal_id is not None:
            row = connection.execute("SELECT status FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row is None or row["status"] != "active":
                raise StateError("state_conflict", "Linked goal must exist and be active")

    @staticmethod
    def _active_slot(connection) -> None:
        if connection.execute("SELECT id FROM runs WHERE status = 'active'").fetchone():
            raise StateError("state_conflict", "Another run is active; wait, hand off, finish or cancel it first")

    def _transition(self, connection, action: str, payload: dict, sequence: int) -> dict:
        if action == "goal.create":
            connection.execute(
                "INSERT INTO goals VALUES (?, ?, 'active', ?, ?, ?)",
                (payload["id"], payload["title"], _json(payload.get("extensions", {})), sequence, sequence),
            )
            return {"goal_id": payload["id"], "status": "active"}
        if action == "task.create":
            self._active_goal(connection, payload["goal_id"])
            connection.execute(
                """INSERT INTO tasks (id, title, goal_id, status, extensions, created_sequence, updated_sequence)
                   VALUES (?, ?, ?, 'ready', ?, ?, ?)""",
                (payload["id"], payload["title"], payload["goal_id"],
                 _json(payload.get("extensions", {})), sequence, sequence),
            )
            return {"task_id": payload["id"], "run_id": None, "status": "ready"}
        task = self._task(connection, payload["task_id"])
        allowed = {
            "task.begin": {"ready"}, "task.wait": {"in-progress"},
            "task.resume": {"waiting-user", "blocked", "handed-off"},
            "task.handoff": {"in-progress"}, "task.finish": {"in-progress"},
            "task.cancel": {"ready", "in-progress", "waiting-user", "blocked", "handed-off", "implemented-unverified"},
        }
        if task["status"] not in allowed[action]:
            raise StateError("state_conflict", f"Cannot {action} a {task['status']} task")
        run_id = task["run_id"]
        next_action = task["next_action"]
        summary = task["summary"]
        cancel_reason = task["cancel_reason"]
        if action in {"task.begin", "task.resume"}:
            self._active_goal(connection, task["goal_id"])
            self._active_slot(connection)
            task_status, run_status = "in-progress", "active"
            next_action = payload["next_action"]
            if action == "task.begin":
                run_id = payload["run_id"]
                connection.execute("INSERT INTO runs VALUES (?, ?, 'active', ?, ?)",
                                   (run_id, task["id"], sequence, sequence))
            else:
                if task["run"] is None:
                    raise StateError("state_conflict", "Resumable task has no run")
                connection.execute(
                    "UPDATE blockers SET resolved_sequence = ? WHERE task_id = ? AND resolved_sequence IS NULL",
                    (sequence, task["id"]),
                )
        elif action == "task.wait":
            task_status = run_status = "waiting-user" if payload["kind"] == "user" else "blocked"
            next_action = "Wait for: " + payload["resume_when"]
            connection.execute(
                """INSERT INTO blockers (task_id, run_id, kind, reason, question_ref, resume_when, created_sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (task["id"], run_id, payload["kind"], payload["reason"],
                 payload.get("question_ref"), payload["resume_when"], sequence),
            )
        elif action == "task.handoff":
            task_status = run_status = "handed-off"
            next_action = payload["next_action"]
        elif action == "task.finish":
            task_status, run_status = "implemented-unverified", "finished"
            summary, next_action = payload["summary"], None
        else:
            task_status = run_status = "cancelled"
            cancel_reason, next_action = payload["reason"], None
            connection.execute(
                "UPDATE blockers SET resolved_sequence = ? WHERE task_id = ? AND resolved_sequence IS NULL",
                (sequence, task["id"]),
            )
        if run_id is not None:
            connection.execute("UPDATE runs SET status = ?, updated_sequence = ? WHERE id = ?",
                               (run_status, sequence, run_id))
        connection.execute(
            """UPDATE tasks SET status = ?, run_id = ?, next_action = ?, summary = ?,
               cancel_reason = ?, updated_sequence = ? WHERE id = ?""",
            (task_status, run_id, next_action, summary, cancel_reason, sequence, task["id"]),
        )
        return {"task_id": task["id"], "run_id": run_id, "status": task_status}

    def apply(self, envelope: dict) -> dict:
        request, canonical, request_hash = _request(envelope)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            previous = connection.execute(
                "SELECT request_json, receipt_json FROM commands WHERE command_id = ?", (request["command_id"],)
            ).fetchone()
            if previous:
                if previous["request_json"] != canonical:
                    raise StateError("command_conflict", "command_id already belongs to a different envelope")
                return json.loads(previous["receipt_json"])
            if metadata["local_revision"] != request["expected_revision"]:
                raise StateError("stale_revision", f"Expected revision {request['expected_revision']}; current is {metadata['local_revision']}")
            if metadata["local_revision"] >= MAX_REVISION:
                raise StateError("state_conflict", "Revision limit reached")
            sequence = metadata["local_revision"] + 1
            result = self._transition(connection, request["action"], request["payload"], sequence)
            origin_context = self.context_id
            origin_revision = sequence
            receipt = {
                "schema_version": SCHEMA_VERSION, "project_id": self.project_id, "context_id": origin_context,
                "command_id": request["command_id"], "revision": origin_revision, "action": request["action"],
                "request_hash": request_hash, "created_at": timestamp, "result": result,
            }
            connection.execute(
                """INSERT INTO commands (command_id, local_sequence, origin_kind, origin_context_id,
                       origin_revision, action, request_json, request_hash, receipt_json, created_at)
                   VALUES (?, ?, 'local', ?, ?, ?, ?, ?, ?, ?)""",
                (request["command_id"], sequence, origin_context, origin_revision,
                 request["action"], canonical, request_hash, _json(receipt), timestamp),
            )
            connection.execute(
                """INSERT INTO events (local_sequence, command_id, origin_kind, origin_context_id,
                       origin_revision, action, request_hash, created_at)
                   VALUES (?, ?, 'local', ?, ?, ?, ?, ?)""",
                (sequence, request["command_id"], origin_context, origin_revision,
                 request["action"], request_hash, timestamp),
            )
            connection.execute("UPDATE metadata SET local_revision = ? WHERE singleton = 1", (sequence,))
            connection.execute(
                """INSERT INTO projection_jobs VALUES (1, ?)
                   ON CONFLICT(singleton) DO UPDATE SET local_revision = excluded.local_revision""", (sequence,)
            )
            connection.commit()
            return receipt

    def ledger(self, after_sequence: int = 0, limit: int = 100) -> list[dict]:
        """Bounded read of immutable command records ordered by local commit sequence."""
        _integer(after_sequence, "after_sequence")
        _limit(limit)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            rows = connection.execute(
                """SELECT local_sequence, origin_kind, origin_context_id, origin_revision, command_id, action,
                          request_json, request_hash, receipt_json, created_at
                   FROM commands WHERE local_sequence > ? ORDER BY local_sequence LIMIT ?""",
                (after_sequence, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def projection_done(self, local_revision: int) -> bool:
        _integer(local_revision, "revision")
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            if metadata["local_revision"] != local_revision:
                return False
            connection.execute(
                "DELETE FROM projection_jobs WHERE singleton = 1 AND local_revision = ?", (local_revision,)
            )
            connection.commit()
            return True

    @staticmethod
    def _exchange(connection) -> dict:
        row = connection.execute("SELECT * FROM exchange WHERE singleton = 1").fetchone()
        if row is None:
            raise StateError("state_conflict", "Missing exchange metadata")
        return dict(row)

    def exchange_state(self) -> dict:
        """Read-only view of the local exchange bookkeeping."""
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            return self._exchange(connection)

    def export_bundle(self) -> dict:
        """One coherent read of every portable record needed for a snapshot."""
        with self._connection() as connection:
            connection.execute("BEGIN")
            metadata = self._metadata(connection)
            exchange = self._exchange(connection)
            return {
                "schema_version": SCHEMA_VERSION,
                "project_id": self.project_id,
                "context_id": self.context_id,
                "local_revision": metadata["local_revision"],
                "base_snapshot": exchange["base_snapshot"],
                "goals": [dict(row) for row in connection.execute("SELECT * FROM goals ORDER BY id")],
                "tasks": [dict(row) for row in connection.execute("SELECT * FROM tasks ORDER BY id")],
                "runs": [dict(row) for row in connection.execute("SELECT * FROM runs ORDER BY id")],
                "blockers": [dict(row) for row in connection.execute("SELECT * FROM blockers ORDER BY id")],
                "ledger": [dict(row) for row in connection.execute(
                    "SELECT * FROM commands ORDER BY local_sequence")],
            }

    def begin_export(self, snapshot_id: str, revision: int) -> dict:
        """Record the publication intent before the pointer is written anywhere."""
        _text(snapshot_id, "snapshot_id", 64)
        _integer(revision, "revision")
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            exchange = self._exchange(connection)
            if exchange["pending_kind"] is not None:
                raise StateError("exchange_pending", f"Pending {exchange['pending_kind']} requires reconciliation")
            if metadata["local_revision"] != revision:
                raise StateError("stale_revision", "Export must snapshot the current local revision")
            connection.execute(
                """UPDATE exchange SET pending_kind = 'export', pending_snapshot = ?,
                   pending_base = ?, pending_revision = ? WHERE singleton = 1""",
                (snapshot_id, exchange["base_snapshot"], revision),
            )
            connection.commit()
            return self._exchange(connection)

    def finish_export(self, snapshot_id: str) -> dict:
        _text(snapshot_id, "snapshot_id", 64)
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._metadata(connection)
            exchange = self._exchange(connection)
            if exchange["pending_kind"] != "export" or exchange["pending_snapshot"] != snapshot_id:
                raise StateError("exchange_conflict", "No matching pending export to acknowledge")
            connection.execute(
                """UPDATE exchange SET base_snapshot = ?, exported_local_revision = ?,
                   pending_kind = NULL, pending_snapshot = NULL, pending_base = NULL,
                   pending_revision = NULL WHERE singleton = 1""",
                (snapshot_id, exchange["pending_revision"]),
            )
            connection.commit()
            return self._exchange(connection)

    def abandon_export(self, reason: str) -> dict:
        """Explicit operator recovery: discard an unacknowledged publication intent."""
        _text(reason, "reason")
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._metadata(connection)
            exchange = self._exchange(connection)
            if exchange["pending_kind"] != "export":
                raise StateError("exchange_conflict", "No pending export to abandon")
            connection.execute(
                """UPDATE exchange SET pending_kind = NULL, pending_snapshot = NULL,
                   pending_base = NULL, pending_revision = NULL WHERE singleton = 1"""
            )
            connection.commit()
            return self._exchange(connection)

    @staticmethod
    def _entity_rows(connection) -> dict:
        return {
            "goals": [dict(row) for row in connection.execute("SELECT * FROM goals ORDER BY id")],
            "tasks": [dict(row) for row in connection.execute("SELECT * FROM tasks ORDER BY id")],
            "runs": [dict(row) for row in connection.execute("SELECT * FROM runs ORDER BY id")],
            "blockers": [dict(row) for row in connection.execute("SELECT * FROM blockers ORDER BY id")],
        }

    @staticmethod
    def _translate_entities(entities: dict, mapping: dict) -> dict:
        def remap(value, label):
            if value is None:
                return None
            if value not in mapping:
                raise StateError("invalid_snapshot", f"{label} references unknown sequence {value}")
            return mapping[value]

        translated = {}
        for name in ("goals", "tasks", "runs"):
            rows = []
            for row in entities[name]:
                row = dict(row)
                row["created_sequence"] = remap(row["created_sequence"], name)
                row["updated_sequence"] = remap(row["updated_sequence"], name)
                rows.append(row)
            translated[name] = rows
        blockers = []
        for row in entities["blockers"]:
            row = dict(row)
            row["created_sequence"] = remap(row["created_sequence"], "blockers")
            row["resolved_sequence"] = remap(row["resolved_sequence"], "blockers")
            blockers.append(row)
        translated["blockers"] = blockers
        return translated

    def apply_import(self, bundle: dict, snapshot_id: str) -> dict:
        """Replace entity state from a verified snapshot and append its new commands.

        Shared commands keep their original receipt bytes; only the receiving
        local sequence is new. Rejection leaves the store untouched.
        """
        bundle = _validate_bundle(bundle)
        _text(snapshot_id, "snapshot_id", 64)
        with self._connection(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            exchange = self._exchange(connection)
            if exchange["pending_kind"] is not None:
                raise StateError("exchange_pending", f"Pending {exchange['pending_kind']} requires reconciliation")
            if bundle["project_id"] != self.project_id:
                raise StateError("foreign_snapshot", "Snapshot belongs to another project identity")
            local = {row["command_id"]: dict(row) for row in connection.execute("SELECT * FROM commands")}
            for row in bundle["ledger"]:
                known = local.get(row["command_id"])
                if known is None:
                    continue
                if any(known[key] != row[key] for key in (
                        "origin_kind", "origin_context_id", "origin_revision", "action",
                        "request_json", "request_hash", "receipt_json", "created_at")):
                    raise StateError("history_rewritten", f"Snapshot rewrites shared command {row['command_id']}")
            mapping = {row["local_sequence"]: local[row["command_id"]]["local_sequence"]
                       for row in bundle["ledger"] if row["command_id"] in local}
            sequence = metadata["local_revision"]
            appended = []
            for row in bundle["ledger"]:
                if row["command_id"] in local:
                    continue
                sequence += 1
                mapping[row["local_sequence"]] = sequence
                appended.append((row, sequence))
            translated = self._translate_entities(bundle, mapping)
            if not appended and translated == self._entity_rows(connection) and exchange["base_snapshot"] == snapshot_id:
                return {"status": "unchanged", "snapshot_id": snapshot_id,
                        "local_revision": metadata["local_revision"], "imported_commands": 0}
            connection.execute("DELETE FROM blockers")
            connection.execute("UPDATE tasks SET run_id = NULL")
            connection.execute("DELETE FROM runs")
            connection.execute("DELETE FROM tasks")
            connection.execute("DELETE FROM goals")
            for row in translated["goals"]:
                connection.execute(
                    "INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["goals"]))
            for row in translated["tasks"]:
                detached = dict(row, run_id=None)
                connection.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(detached[column] for column in _BUNDLE_COLUMNS["tasks"]))
            for row in translated["runs"]:
                connection.execute(
                    "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["runs"]))
            for row in translated["tasks"]:
                if row["run_id"] is not None:
                    connection.execute("UPDATE tasks SET run_id = ? WHERE id = ?", (row["run_id"], row["id"]))
            for row in translated["blockers"]:
                connection.execute(
                    "INSERT INTO blockers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["blockers"]))
            for row, assigned in appended:
                connection.execute(
                    """INSERT INTO commands (command_id, local_sequence, origin_kind, origin_context_id,
                           origin_revision, action, request_json, request_hash, receipt_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (row["command_id"], assigned, row["origin_kind"], row["origin_context_id"],
                     row["origin_revision"], row["action"], row["request_json"], row["request_hash"],
                     row["receipt_json"], row["created_at"]))
                connection.execute(
                    """INSERT INTO events (local_sequence, command_id, origin_kind, origin_context_id,
                           origin_revision, action, request_hash, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (assigned, row["command_id"], row["origin_kind"], row["origin_context_id"],
                     row["origin_revision"], row["action"], row["request_hash"], row["created_at"]))
            connection.execute("UPDATE metadata SET local_revision = ? WHERE singleton = 1", (sequence,))
            connection.execute(
                """INSERT INTO projection_jobs VALUES (1, ?)
                   ON CONFLICT(singleton) DO UPDATE SET local_revision = excluded.local_revision""",
                (sequence,))
            connection.execute(
                """UPDATE exchange SET base_snapshot = ?, exported_local_revision = ?,
                   pending_kind = NULL, pending_snapshot = NULL, pending_base = NULL,
                   pending_revision = NULL WHERE singleton = 1""",
                (snapshot_id, sequence))
            problems = self._verify_ledger(connection)
            if problems:
                raise StateError("invalid_snapshot", problems[0])
            connection.commit()
            return {"status": "imported", "snapshot_id": snapshot_id,
                    "local_revision": sequence, "imported_commands": len(appended)}

    def validate(self) -> list[str]:
        """Return diagnostics, or an empty list; audit never repairs authority."""
        try:
            self._audit()
        except (StateError, ValueError, TypeError, KeyError) as error:
            return [str(error)]
        return []

    def _verify_ledger(self, connection) -> list[str]:
        """Replay the ledger against the entity tables on one connection.

        Shared by the read-only audit and by import validation, so a snapshot
        can never be accepted into a store that then fails its own audit.
        """
        metadata = self._metadata(connection)
        problems: list[str] = []
        run_links = {row["id"]: row["run_id"] for row in connection.execute("SELECT id, run_id FROM tasks")}
        created_goals: set[str] = set()
        created_tasks: set[str] = set()
        begun_runs: dict[str, str] = {}
        waited: list[tuple[str, str]] = []
        position = 0
        offset = 0
        while True:
            rows = connection.execute(
                """SELECT commands.*, events.command_id AS event_command, events.action AS event_action,
                   events.request_hash AS event_hash, events.created_at AS event_time,
                   events.origin_kind AS event_origin_kind,
                   events.origin_context_id AS event_origin_context,
                   events.origin_revision AS event_origin_revision
                   FROM commands LEFT JOIN events ON events.local_sequence = commands.local_sequence
                   ORDER BY commands.local_sequence LIMIT ? OFFSET ?""",
                (MAX_LIMIT, offset),
            ).fetchall()
            if not rows:
                break
            offset += len(rows)
            for row in rows:
                position += 1
                try:
                    request, canonical, digest = _request(json.loads(row["request_json"]))
                    receipt = json.loads(row["receipt_json"])
                    payload = request["payload"]
                    action = request["action"]
                    task_id = payload.get("task_id", payload.get("id"))
                    if action == "goal.create":
                        run_id = None
                        result = {"goal_id": payload["id"], "status": "active"}
                        created_goals.add(payload["id"])
                    else:
                        status = {
                            "task.create": "ready", "task.begin": "in-progress", "task.resume": "in-progress",
                            "task.wait": "waiting-user" if payload.get("kind") == "user" else "blocked",
                            "task.handoff": "handed-off", "task.finish": "implemented-unverified",
                            "task.cancel": "cancelled",
                        }[action]
                        if action == "task.create":
                            run_id = None
                            created_tasks.add(task_id)
                        elif task_id in run_links:
                            run_id = run_links[task_id]
                        else:
                            raise ValueError("Receipt references an unknown task")
                        if action == "task.begin":
                            if run_id != payload["run_id"]:
                                raise ValueError("Begin receipt run disagrees with the authoritative task run")
                            begun_runs[payload["run_id"]] = task_id
                        elif action == "task.wait":
                            waited.append((task_id, payload["kind"]))
                        result = {"task_id": task_id, "run_id": run_id, "status": status}
                    expected = {
                        "schema_version": SCHEMA_VERSION, "project_id": self.project_id,
                        "context_id": row["origin_context_id"], "command_id": row["command_id"],
                        "revision": row["origin_revision"], "action": row["action"],
                        "request_hash": digest, "created_at": row["created_at"], "result": result,
                    }
                    local_chain = row["origin_kind"] == "local" and row["origin_context_id"] == self.context_id
                    if (row["local_sequence"] != position
                            or (local_chain and (row["origin_revision"] != row["local_sequence"]
                                                 or request["expected_revision"] != row["origin_revision"] - 1))
                            or canonical != row["request_json"] or digest != row["request_hash"]
                            or request["command_id"] != row["command_id"] or request["action"] != row["action"]
                            or row["event_command"] != row["command_id"] or row["event_action"] != row["action"]
                            or row["event_hash"] != digest or row["event_time"] != row["created_at"]
                            or row["event_origin_kind"] != row["origin_kind"]
                            or row["event_origin_context"] != row["origin_context_id"]
                            or row["event_origin_revision"] != row["origin_revision"]
                            or receipt["context_id"] != row["origin_context_id"]
                            or receipt["revision"] != row["origin_revision"]
                            or _json(receipt) != _json(expected)):
                        raise ValueError("Ledger header mismatch")
                except (ValueError, TypeError, KeyError) as error:
                    problems.append(
                        f"Invalid receipt/event at local sequence {row['local_sequence']}: {error}"
                    )
        if position != metadata["local_revision"]:
            problems.append("Local revision/receipt cardinality mismatch")
        goals = {row["id"] for row in connection.execute("SELECT id FROM goals")}
        tasks = {row["id"] for row in connection.execute("SELECT id FROM tasks")}
        runs = {row["id"]: row["task_id"] for row in connection.execute("SELECT id, task_id FROM runs")}
        blockers = sorted(
            (row["task_id"], row["kind"]) for row in connection.execute("SELECT task_id, kind FROM blockers")
        )
        if goals != created_goals:
            problems.append("Ledger and entity tables disagree on goals")
        if tasks != created_tasks:
            problems.append("Ledger and entity tables disagree on tasks")
        if runs != begun_runs:
            problems.append("Ledger and entity tables disagree on runs")
        if blockers != sorted(waited):
            problems.append("Ledger and entity tables disagree on blockers")
        return problems

    def _audit(self) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN")
            metadata = self._metadata(connection)
            if any(row[0] != "ok" for row in connection.execute("PRAGMA integrity_check")):
                raise StateError("state_conflict", "SQLite integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise StateError("state_conflict", "Foreign key check failed")
            invalid = connection.execute(
                """SELECT tasks.id FROM tasks LEFT JOIN runs ON runs.id = tasks.run_id
                   LEFT JOIN blockers ON blockers.task_id = tasks.id AND blockers.resolved_sequence IS NULL
                   LEFT JOIN goals ON goals.id = tasks.goal_id
                   WHERE (tasks.status = 'ready' AND tasks.run_id IS NOT NULL)
                   OR (tasks.status NOT IN ('ready','cancelled') AND runs.id IS NULL)
                   OR (runs.id IS NOT NULL AND (runs.task_id != tasks.id OR runs.status != CASE tasks.status
                       WHEN 'in-progress' THEN 'active' WHEN 'implemented-unverified' THEN 'finished'
                       ELSE tasks.status END))
                   OR (tasks.status IN ('waiting-user','blocked') AND blockers.id IS NULL)
                   OR (tasks.status NOT IN ('waiting-user','blocked') AND blockers.id IS NOT NULL)
                   OR (blockers.id IS NOT NULL AND (blockers.run_id != tasks.run_id
                       OR (tasks.status = 'waiting-user') != (blockers.kind = 'user')))
                   OR (tasks.status = 'in-progress' AND tasks.goal_id IS NOT NULL AND goals.status != 'active')
                   OR (tasks.status IN ('in-progress','handed-off') AND
                       (tasks.next_action IS NULL OR length(trim(tasks.next_action)) = 0))
                   OR (tasks.status = 'implemented-unverified' AND
                       (tasks.summary IS NULL OR length(trim(tasks.summary)) = 0))
                   OR (tasks.status = 'cancelled' AND
                       (tasks.cancel_reason IS NULL OR length(trim(tasks.cancel_reason)) = 0))
                   LIMIT 1"""
            ).fetchone()
            orphan = connection.execute(
                "SELECT runs.id FROM runs JOIN tasks ON tasks.id = runs.task_id WHERE tasks.run_id IS NOT runs.id LIMIT 1"
            ).fetchone()
            active_count = connection.execute("SELECT count(*) FROM runs WHERE status = 'active'").fetchone()[0]
            if invalid or orphan or active_count > 1:
                raise StateError("state_conflict", "Task/run/blocker lifecycle invariant failed")
            for table in ("goals", "tasks", "runs"):
                if connection.execute(
                    f"SELECT 1 FROM {table} WHERE created_sequence < 1 OR updated_sequence < created_sequence OR updated_sequence > ? LIMIT 1",
                    (metadata["local_revision"],),
                ).fetchone():
                    raise StateError("state_conflict", f"Invalid {table} sequence bounds")
            if connection.execute(
                """SELECT 1 FROM blockers WHERE created_sequence < 1 OR created_sequence > ?
                   OR resolved_sequence < created_sequence OR resolved_sequence > ? LIMIT 1""",
                (metadata["local_revision"], metadata["local_revision"]),
            ).fetchone():
                raise StateError("state_conflict", "Invalid blocker sequence bounds")
            pending = connection.execute("SELECT local_revision FROM projection_jobs WHERE singleton = 1").fetchone()
            if pending and pending[0] != metadata["local_revision"]:
                raise StateError("state_conflict", "Projection job does not match current revision")
            exchange = self._exchange(connection)
            if exchange["exported_local_revision"] > metadata["local_revision"]:
                raise StateError("state_conflict", "Exported revision exceeds the local revision")
            if exchange["pending_revision"] is not None and not 0 < exchange["pending_revision"] <= metadata["local_revision"]:
                raise StateError("state_conflict", "Pending publication revision is outside the accepted range")
            if (connection.execute("SELECT count(*) FROM commands").fetchone()[0] != metadata["local_revision"]
                    or connection.execute("SELECT count(*) FROM events").fetchone()[0] != metadata["local_revision"]):
                raise StateError("state_conflict", "Local revision/receipt/event cardinality mismatch")
            problems = self._verify_ledger(connection)
            if problems:
                raise StateError("state_conflict", problems[0])
        with self._connection() as connection:
            connection.execute("BEGIN")
            if self._metadata(connection)["local_revision"] != metadata["local_revision"]:
                raise StateError("concurrent_change", "Store changed during audit; validate again")
