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
# 3 adds the lifecycle record/evidence/review tables of the promoted format.
STORE_SCHEMA = 3
MAX_LIMIT = 100
MAX_REQUEST_BYTES = 65536
MAX_REVISION = 9223372036854775806
BUSY_TIMEOUT_MS = 5000
# Long-form text belongs in Git; a record payload only carries state and references.
MAX_RECORD_PAYLOAD_BYTES = 16384
MAX_DOCUMENT_BODY_CHARS = 4096

RECORD_KINDS = {
    "business-atom": ("draft", "active", "experimental", "deprecated", "archived", "conflict"),
    "requirement": ("draft", "active", "superseded", "archived"),
    "decision": ("proposed", "active", "experimental", "rejected", "superseded", "archived"),
    "architecture": ("draft", "active", "superseded", "archived"),
    "research": ("draft", "complete", "superseded", "archived"),
    "alignment": ("open", "resolved", "accepted", "archived"),
    "retrospective": ("draft", "complete", "archived"),
    "distillation": ("candidate", "approved", "rejected", "encoded", "archived"),
}
RECORD_RELATIONS = (
    "references", "depends-on", "supersedes", "implements",
    "verifies", "derived-from", "blocks", "aligns",
)
EVIDENCE_STATES = ("candidate", "valid", "failed", "stale", "superseded", "invalid")
REVIEW_VERDICTS = ("go", "no-go", "conditional")
DOCUMENT_BODY_KEYS = ("body", "content", "markdown")


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


def _record_payload(value) -> str:
    """Serialize a record payload; long-form text belongs in Git, not in the store."""
    if type(value) is not dict:
        raise StateError("invalid_input", "payload must be an object")
    _reject_long_form_text(value)
    encoded = _json(value)
    if len(encoded.encode("utf-8")) > MAX_RECORD_PAYLOAD_BYTES:
        raise StateError("invalid_input", f"record payload exceeds {MAX_RECORD_PAYLOAD_BYTES} encoded bytes")
    return encoded


def _reject_long_form_text(value, path: str = "payload") -> None:
    """Reject long-form text anywhere in a record payload, nested objects included.

    Checking only the top-level ``body``/``content``/``markdown`` keys let a caller
    hide a second copy of a document under ``payload.meta.body``; the boundary has
    to hold at every depth or it does not hold at all.
    """
    if type(value) is dict:
        for key, item in value.items():
            _reject_long_form_text(item, f"{path}.{key}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _reject_long_form_text(item, f"{path}[{index}]")
        return
    if type(value) is not str:
        return
    if len(value.encode("utf-8")) <= MAX_DOCUMENT_BODY_CHARS:
        return
    raise StateError(
        "document_body_not_allowed",
        f"{path} carries {len(value.encode('utf-8'))} bytes of long-form text; "
        "store a doc_ref instead",
    )


def _iter_doc_refs(value, path: str = "payload"):
    """Yield ``doc_ref`` objects anywhere in a record payload."""
    if type(value) is dict:
        if set(value) >= {"path", "sha256"} and type(value.get("path")) is str:
            yield path, value
        for key, item in value.items():
            yield from _iter_doc_refs(item, f"{path}.{key}")
    elif type(value) is list:
        for index, item in enumerate(value):
            yield from _iter_doc_refs(item, f"{path}[{index}]")


def _doc_ref_issues(root: Path | None, payload) -> list[dict]:
    """Re-evaluate every ``doc_ref`` recorded in a record payload.

    The stored hash is what makes a reference load-bearing: without re-computing it
    a long document can drift while the structured record still claims to describe it.
    """
    if root is None:
        return []
    base = Path(root)
    issues: list[dict] = []
    for reference_path, reference in _iter_doc_refs(payload):
        path = reference.get("path")
        expected = reference.get("sha256")
        if type(path) is not str or type(expected) is not str or not expected:
            issues.append({
                "reference": reference_path, "path": path,
                "reason": "doc_ref must carry path and sha256",
            })
            continue
        target = Path(path)
        if not target.is_absolute():
            target = base / target
        try:
            if target.is_symlink() or not target.is_file():
                raise OSError("missing")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError as error:
            issues.append({
                "reference": reference_path, "path": path,
                "reason": f"doc_ref is unreadable: {error}",
            })
            continue
        if actual != expected:
            issues.append({
                "reference": reference_path, "path": path,
                "reason": f"doc_ref changed: recorded {expected[:12]}, current {actual[:12]}",
            })
    return issues


def _record_kind_status(kind, status) -> tuple[str, str]:
    if type(kind) is not str or kind not in RECORD_KINDS:
        raise StateError("unsupported_record_kind", f"Unsupported record kind: {kind!r}")
    if type(status) is not str or status not in RECORD_KINDS[kind]:
        raise StateError("invalid_input", f"Status {status!r} is not valid for record kind {kind!r}")
    return kind, status


def _record_governance(kind: str, payload: dict) -> None:
    """C-level decisions and requirement baselines must carry their approval."""
    if kind == "decision" and payload.get("authority") == "C" and payload.get("user_approval") != "approved":
        raise StateError("invalid_input", "A C-level decision record requires user_approval=approved")
    if kind == "requirement":
        approval = payload.get("approval")
        if type(approval) is not dict or approval.get("status") not in {
            "pending", "approved", "rejected", "experimental",
        }:
            raise StateError("invalid_input", "A requirement record must carry approval.status")


def _evidence_covers(value) -> str:
    if value is None:
        value = {}
    if type(value) is not dict or set(value) - {"files", "requirements", "tasks"}:
        raise StateError("invalid_input", "covers must be an object with files/requirements/tasks")
    normalized = {}
    for key in ("files", "requirements", "tasks"):
        items = value.get(key, [])
        if type(items) is not list or any(type(item) is not str for item in items):
            raise StateError("invalid_input", f"covers.{key} must be a list of strings")
        normalized[key] = items
    return _json(normalized)


def _version_binding(value) -> str:
    if value is None:
        value = {}
    if type(value) is not dict or set(value) - {"git_commit", "diff_hash", "file_hashes"}:
        raise StateError("invalid_input", "version_binding must be an object with git_commit/diff_hash/file_hashes")
    for key in ("git_commit", "diff_hash"):
        if value.get(key) is not None and type(value[key]) is not str:
            raise StateError("invalid_input", f"version_binding.{key} must be text or null")
    hashes = value.get("file_hashes", {})
    if type(hashes) is not dict or any(
        type(key) is not str or type(item) is not str for key, item in hashes.items()
    ):
        raise StateError("invalid_input", "version_binding.file_hashes must map paths to hashes")
    return _json(value)


def _evidence_refs(value) -> str:
    if type(value) is not list or any(type(item) is not str or not item.strip() for item in value):
        raise StateError("invalid_input", "evidence_refs must be a list of nonempty strings")
    return _json(value)


def _decode_json(value: str, name: str):
    try:
        return json.loads(value)
    except (TypeError, ValueError, UnicodeError) as error:
        raise StateError("state_conflict", f"Stored {name} is not valid JSON") from error


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
        "goal.update": ({"id"}, {"success_conditions", "required_evidence"}),
        "goal.complete": ({"id"}, set()),
        "task.create": ({"id", "title", "goal_id"}, {"extensions"}),
        "task.update": ({"task_id"}, {"implementer", "owner"}),
        "task.begin": ({"task_id", "run_id", "next_action"}, set()),
        "task.wait": ({"task_id", "kind", "reason", "resume_when"}, {"question_ref"}),
        "task.resume": ({"task_id", "next_action"}, set()),
        "task.handoff": ({"task_id", "next_action"}, set()),
        "task.finish": ({"task_id", "summary"}, set()),
        "task.cancel": ({"task_id", "reason"}, set()),
        "record.create": ({"kind", "id", "title", "status"}, {"payload"}),
        "record.update": ({"kind", "id", "expected_record_revision"}, {"status", "payload"}),
        "record.link": ({"from_kind", "from_id", "relation", "to_kind", "to_id"}, set()),
        "evidence.record": ({"id", "kind", "subject", "status"}, {"task_id", "covers", "version_binding"}),
        "evidence.invalidate": ({"id", "reason"}, set()),
        "review.record": ({"id", "task_id", "reviewer", "verdict", "scope", "evidence_refs"}, set()),
    }
    if action not in shapes:
        raise StateError("unsupported_action", f"Unsupported action: {action}")
    payload = envelope["payload"]
    required, optional = shapes[action]
    if type(payload) is not dict or not required <= set(payload) or set(payload) - required - optional:
        raise StateError("invalid_input", f"{action} payload has missing or unknown fields")
    for key, value in payload.items():
        if key in {"extensions", "payload", "covers", "version_binding", "scope"}:
            if type(value) is not dict:
                raise StateError("invalid_input", f"{key} must be an object")
        elif key == "evidence_refs":
            _evidence_refs(value)
        elif key in {"success_conditions", "required_evidence"}:
            if type(value) is not list:
                raise StateError("invalid_input", f"{key} must be a list")
        elif key == "expected_record_revision":
            _integer(value, key)
        elif key in {"goal_id", "task_id"} and value is None:
            continue
        else:
            maximum = 256 if key in {
                "id", "task_id", "run_id", "goal_id", "question_ref",
                "kind", "from_kind", "from_id", "to_kind", "to_id",
            } else 8192
            _text(value, key, maximum)
    if action == "task.wait":
        if payload["kind"] not in {"user", "dependency", "environment"}:
            raise StateError("invalid_input", "Unknown wait kind")
        if (payload["kind"] == "user") != ("question_ref" in payload):
            raise StateError("invalid_input", "question_ref is required only for user waits")
    elif action in {"record.create", "record.update"}:
        kind = payload["kind"]
        if action == "record.create":
            status = payload["status"]
        else:
            status = payload.get("status")
            if status is None and "payload" not in payload:
                raise StateError("invalid_input", "record.update requires status or payload")
        if status is not None:
            _record_kind_status(kind, status)
        elif kind not in RECORD_KINDS:
            raise StateError("unsupported_record_kind", f"Unsupported record kind: {kind!r}")
        if action == "record.create":
            _record_governance(kind, payload.get("payload", {}))
    elif action == "record.link":
        if payload["relation"] not in RECORD_RELATIONS:
            raise StateError("invalid_input", f"Unsupported relation: {payload['relation']}")
        for key in ("from_kind", "to_kind"):
            if payload[key] not in RECORD_KINDS:
                raise StateError("unsupported_record_kind", f"Unsupported record kind: {payload[key]!r}")
    elif action == "evidence.record":
        if payload["status"] not in EVIDENCE_STATES:
            raise StateError("invalid_input", f"Unsupported evidence status: {payload['status']}")
        _evidence_covers(payload.get("covers"))
        _version_binding(payload.get("version_binding"))
    elif action == "review.record":
        if payload["verdict"] not in REVIEW_VERDICTS:
            raise StateError("invalid_input", f"Unsupported review verdict: {payload['verdict']}")
    elif action == "task.update":
        if not ({"implementer", "owner"} & set(payload)):
            raise StateError("invalid_input", "task.update requires implementer or owner")
    elif action == "goal.update":
        if not ({"success_conditions", "required_evidence"} & set(payload)):
            raise StateError(
                "invalid_input", "goal.update requires success_conditions or required_evidence"
            )
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
    "records": ("kind", "id", "title", "status", "revision", "payload",
                "created_sequence", "updated_sequence"),
    "record_links": ("from_kind", "from_id", "relation", "to_kind", "to_id", "created_sequence"),
    "evidence": ("id", "task_id", "kind", "subject", "status", "covers", "version_binding",
                 "recorded_sequence", "invalidated_sequence", "invalidation_reason"),
    "reviews": ("id", "task_id", "reviewer", "verdict", "scope", "evidence_refs",
                "created_sequence"),
    "ledger": ("local_sequence", "command_id", "origin_kind", "origin_context_id", "origin_revision",
               "action", "request_json", "request_hash", "receipt_json", "created_at"),
}
_BUNDLE_FIELDS = {"schema_version", "project_id", "context_id", "local_revision", "base_snapshot"} | set(_BUNDLE_COLUMNS)
_BUNDLE_INTEGERS = {
    "local_sequence", "origin_revision", "created_sequence", "updated_sequence",
    "resolved_sequence", "revision", "recorded_sequence", "invalidated_sequence",
}


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
        store_schema INTEGER NOT NULL CHECK(store_schema = 3),
        schema_version INTEGER NOT NULL CHECK(schema_version = 1),
        project_id TEXT NOT NULL, context_id TEXT NOT NULL,
        local_revision INTEGER NOT NULL CHECK(local_revision >= 0))""",
    """CREATE TABLE goals (
        id TEXT PRIMARY KEY, title TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('draft','active','waiting-user','blocked','complete')),
        extensions TEXT NOT NULL,
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
    """CREATE TABLE records (
        kind TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
        status TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1),
        payload TEXT NOT NULL, created_sequence INTEGER NOT NULL,
        updated_sequence INTEGER NOT NULL,
        PRIMARY KEY (kind, id))""",
    """CREATE TABLE record_links (
        from_kind TEXT NOT NULL, from_id TEXT NOT NULL, relation TEXT NOT NULL,
        to_kind TEXT NOT NULL, to_id TEXT NOT NULL, created_sequence INTEGER NOT NULL,
        PRIMARY KEY (from_kind, from_id, relation, to_kind, to_id),
        FOREIGN KEY (from_kind, from_id) REFERENCES records(kind, id),
        FOREIGN KEY (to_kind, to_id) REFERENCES records(kind, id))""",
    """CREATE TABLE evidence (
        id TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(id),
        kind TEXT NOT NULL, subject TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN
            ('candidate','valid','failed','stale','superseded','invalid')),
        covers TEXT NOT NULL, version_binding TEXT NOT NULL,
        recorded_sequence INTEGER NOT NULL, invalidated_sequence INTEGER,
        invalidation_reason TEXT,
        CHECK((invalidated_sequence IS NULL) = (invalidation_reason IS NULL)))""",
    """CREATE TABLE reviews (
        id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
        reviewer TEXT NOT NULL,
        verdict TEXT NOT NULL CHECK(verdict IN ('go','no-go','conditional')),
        scope TEXT NOT NULL, evidence_refs TEXT NOT NULL,
        created_sequence INTEGER NOT NULL)""",
    "CREATE INDEX records_recent ON records(updated_sequence DESC, kind, id)",
    "CREATE INDEX evidence_task ON evidence(task_id)",
    "CREATE INDEX reviews_task ON reviews(task_id, created_sequence DESC)",
)


class Store:
    """One explicitly initialized database bound to one project and branch context."""

    def __init__(self, path: Path, project_id: str, context_id: str, root: Path | None = None):
        self.path = native_path(path)
        self.project_id = _text(project_id, "project_id", 256)
        self.context_id = _text(context_id, "context_id", 256)
        # The worktree root is required to re-evaluate evidence applicability.
        # Stores built directly in tests may omit it; the CLI always supplies it.
        self.root: Path | None = Path(root).resolve() if root is not None else None

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

    def active_goal_id(self) -> str:
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            row = connection.execute(
                "SELECT id FROM goals WHERE status = 'active' ORDER BY created_sequence LIMIT 1"
            ).fetchone()
            if row is None:
                raise StateError("not_found", "No active goal")
            return row["id"]

    def get_goal(self, goal_id: str) -> dict:
        _text(goal_id, "goal_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            row = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown goal: {goal_id}")
            goal = dict(row)
            goal["extensions"] = _decode_json(goal["extensions"], "goal extensions")
            return goal

    @staticmethod
    def _record(row) -> dict:
        record = dict(row)
        record["payload"] = _decode_json(record["payload"], "record payload")
        return record

    @staticmethod
    def _evidence(row) -> dict:
        evidence = dict(row)
        evidence["covers"] = _decode_json(evidence["covers"], "evidence covers")
        evidence["version_binding"] = _decode_json(
            evidence["version_binding"], "evidence version binding"
        )
        return evidence

    @staticmethod
    def _review(row) -> dict:
        review = dict(row)
        review["scope"] = _decode_json(review["scope"], "review scope")
        review["evidence_refs"] = _decode_json(review["evidence_refs"], "review evidence refs")
        return review

    def get_record(self, kind: str, record_id: str) -> dict:
        if kind not in RECORD_KINDS:
            raise StateError("unsupported_record_kind", f"Unsupported record kind: {kind!r}")
        _text(record_id, "record_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            row = connection.execute(
                "SELECT * FROM records WHERE kind = ? AND id = ?", (kind, record_id)
            ).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown record: {kind}/{record_id}")
            return self._record(row)

    def list_records(self, kind: str | None = None) -> list[dict]:
        if kind is not None and kind not in RECORD_KINDS:
            raise StateError("unsupported_record_kind", f"Unsupported record kind: {kind!r}")
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            if kind is None:
                rows = connection.execute(
                    "SELECT * FROM records ORDER BY updated_sequence DESC, kind, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM records WHERE kind = ? ORDER BY updated_sequence DESC, id",
                    (kind,),
                ).fetchall()
            return [self._record(row) for row in rows]

    def list_record_links(self, kind: str | None = None, record_id: str | None = None) -> list[dict]:
        if kind is not None and kind not in RECORD_KINDS:
            raise StateError("unsupported_record_kind", f"Unsupported record kind: {kind!r}")
        if record_id is not None:
            _text(record_id, "record_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            if kind is None and record_id is None:
                rows = connection.execute(
                    "SELECT * FROM record_links ORDER BY created_sequence, from_kind, from_id, relation, to_kind, to_id"
                ).fetchall()
            elif kind is None:
                rows = connection.execute(
                    """SELECT * FROM record_links WHERE from_id = ? OR to_id = ?
                       ORDER BY created_sequence, from_kind, from_id, relation, to_kind, to_id""",
                    (record_id, record_id),
                ).fetchall()
            elif record_id is None:
                rows = connection.execute(
                    """SELECT * FROM record_links WHERE from_kind = ? OR to_kind = ?
                       ORDER BY created_sequence, from_kind, from_id, relation, to_kind, to_id""",
                    (kind, kind),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM record_links
                       WHERE (from_kind = ? AND from_id = ?) OR (to_kind = ? AND to_id = ?)
                       ORDER BY created_sequence, from_kind, from_id, relation, to_kind, to_id""",
                    (kind, record_id, kind, record_id),
                ).fetchall()
            return [dict(row) for row in rows]

    def get_evidence(self, evidence_id: str) -> dict:
        _text(evidence_id, "evidence_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            row = connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown evidence: {evidence_id}")
            return self._evidence(row)

    def list_evidence(self, task_id: str | None = None) -> list[dict]:
        if task_id is not None:
            _text(task_id, "task_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            if task_id is None:
                rows = connection.execute(
                    "SELECT * FROM evidence ORDER BY recorded_sequence DESC, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM evidence WHERE task_id = ? OR task_id IS NULL
                       ORDER BY recorded_sequence DESC, id""",
                    (task_id,),
                ).fetchall()
            return [self._evidence(row) for row in rows]

    @staticmethod
    def evidence_applicability(root: Path, evidence: dict) -> dict:
        """Compare recorded file hashes with the current worktree."""
        binding = evidence.get("version_binding")
        hashes = binding.get("file_hashes") if type(binding) is dict else None
        if type(hashes) is not dict or not hashes:
            return {"applicability": "unknown", "reasons": ["no recorded file hashes"]}
        base = Path(root)
        reasons: list[str] = []
        for path, expected in hashes.items():
            if type(path) is not str or type(expected) is not str or not expected:
                reasons.append(f"invalid recorded hash for {path!r}")
                continue
            target = Path(path)
            if not target.is_absolute():
                target = base / target
            try:
                if target.is_symlink() or not target.is_file():
                    reasons.append(f"covered input is missing: {path}")
                    continue
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError as error:
                reasons.append(f"covered input is unreadable: {path}: {error}")
                continue
            if actual != expected:
                reasons.append(f"covered input changed: {path}")
        return {
            "applicability": "stale" if reasons else "current",
            "reasons": reasons,
        }

    def stale_evidence(self, root: Path) -> list[dict]:
        """Read-only list of active evidence whose recorded bytes changed."""
        result = []
        for evidence in self.list_evidence():
            if evidence["status"] not in {"candidate", "valid"}:
                continue
            verdict = self.evidence_applicability(root, evidence)
            if verdict["applicability"] == "stale":
                result.append({"id": evidence["id"], "reasons": verdict["reasons"]})
        return result

    def stale_documents(self, root: Path | None = None) -> list[dict]:
        """Read-only list of record ``doc_ref`` entries whose recorded hash no longer matches.

        Section 4 of the production contract stores long-form text by reference and
        records the hash at write time; re-computing it is the only way the reference
        stays load-bearing instead of decorative.
        """
        base = Path(root) if root is not None else self.root
        if base is None:
            return []
        base = Path(base)
        result: list[dict] = []
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            rows = connection.execute(
                "SELECT kind, id, payload FROM records ORDER BY kind, id"
            ).fetchall()
        for row in rows:
            payload = _decode_json(row["payload"], "record payload")
            for reference_path, reference in _iter_doc_refs(payload):
                path = reference.get("path")
                expected = reference.get("sha256")
                if type(path) is not str or type(expected) is not str or not expected:
                    result.append({
                        "kind": row["kind"], "id": row["id"], "reference": reference_path,
                        "path": path, "reason": "doc_ref must carry path and sha256",
                    })
                    continue
                target = Path(path)
                if not target.is_absolute():
                    target = base / target
                try:
                    if target.is_symlink() or not target.is_file():
                        raise OSError("missing")
                    actual = hashlib.sha256(target.read_bytes()).hexdigest()
                except OSError as error:
                    result.append({
                        "kind": row["kind"], "id": row["id"], "reference": reference_path,
                        "path": path, "reason": f"doc_ref is unreadable: {error}",
                    })
                    continue
                if actual != expected:
                    result.append({
                        "kind": row["kind"], "id": row["id"], "reference": reference_path,
                        "path": path,
                        "reason": f"doc_ref changed: recorded {expected[:12]}, current {actual[:12]}",
                    })
        return result

    def gate_task(self, task_id: str) -> dict:
        _text(task_id, "task_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            task = self._task(connection, task_id)
            problems = self._task_completion_problems(connection, task, self.root)
            return {
                "task_id": task_id,
                "decision": "blocked" if problems else "allowed",
                "blocking": problems,
            }

    def evaluate_goal(self, goal_id: str) -> dict:
        _text(goal_id, "goal_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            problems = self._goal_completion_problems(connection, goal_id, self.root)
            return {
                "goal_id": goal_id,
                "passed": not problems,
                "reasons": problems,
            }

    def audit_gates(self) -> list[str]:
        """Re-evaluate completion claims against current evidence and reviews."""
        errors: list[str] = []
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            for row in connection.execute(
                "SELECT * FROM tasks WHERE status = 'implemented-unverified' ORDER BY id"
            ):
                task = self._task(connection, row["id"])
                for problem in self._task_completion_problems(connection, task, self.root):
                    errors.append(f"task {task['id']}: {problem}")
            for row in connection.execute(
                "SELECT id FROM goals WHERE status = 'complete' ORDER BY id"
            ):
                for problem in self._goal_completion_problems(connection, row["id"], self.root):
                    errors.append(f"goal {row['id']}: {problem}")
        for item in self.stale_documents():
            errors.append(f"record {item['kind']}/{item['id']} {item['reference']}: {item['reason']}")
        return errors

    def list_reviews(self, task_id: str | None = None) -> list[dict]:
        if task_id is not None:
            _text(task_id, "task_id", 256)
        with self._connection() as connection:
            connection.execute("BEGIN")
            self._metadata(connection)
            if task_id is None:
                rows = connection.execute(
                    "SELECT * FROM reviews ORDER BY created_sequence DESC, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM reviews WHERE task_id = ? ORDER BY created_sequence DESC, id",
                    (task_id,),
                ).fetchall()
            return [self._review(row) for row in rows]

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
        latest = connection.execute(
            "SELECT * FROM runs ORDER BY updated_sequence DESC, id DESC LIMIT 1"
        ).fetchone()
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
            "latest_run": dict(latest) if latest else None,
            "latest_task": self._task(connection, latest["task_id"]) if latest else None,
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

    @staticmethod
    def _evidence_covers_task(connection, task_id: str) -> list[dict]:
        matches = []
        for row in connection.execute("SELECT * FROM evidence ORDER BY recorded_sequence"):
            covers = _decode_json(row["covers"], "evidence covers")
            tasks = covers.get("tasks") if type(covers) is dict else None
            if type(tasks) is list and task_id in tasks:
                matches.append(dict(row))
        return matches

    @staticmethod
    def _goal_completion_problems(connection, goal_id: str, root: Path | None = None) -> list[str]:
        row = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if row is None:
            raise StateError("not_found", f"Unknown goal: {goal_id}")
        extensions = _decode_json(row["extensions"], "goal extensions")
        if type(extensions) is not dict:
            return ["goal extensions must be an object"]
        evidence = {
            item["id"]: item for item in (
                dict(row) for row in connection.execute("SELECT * FROM evidence")
            )
        }

        def evidence_status(reference: str) -> str | None:
            """Return the effective status; None when the reference does not exist."""
            item = evidence.get(reference)
            if item is None:
                return None
            if item["status"] != "valid":
                return item["status"]
            if Store._stale_reasons(root, Store._evidence(item)):
                return "stale"
            return "valid"

        problems: list[str] = Store._document_drift_problems(connection, root)
        conditions = extensions.get("success_conditions", [])
        if type(conditions) is not list:
            problems.append("success_conditions must be a list")
            conditions = []
        if not conditions:
            problems.append("goal has no success_conditions")
        for condition in conditions:
            if type(condition) is not dict:
                problems.append("success condition is not an object")
                continue
            condition_id = condition.get("id") or "unnamed condition"
            status = condition.get("status")
            if status not in {"passed", "not-applicable"}:
                problems.append(f"{condition_id}: success condition is {status!r}")
            if status == "not-applicable":
                reason = condition.get("reason") or condition.get("limitation")
                if type(reason) is not str or not reason.strip():
                    problems.append(f"{condition_id}: not-applicable condition has no reason")
            references = condition.get("evidence_refs", [])
            if type(references) is not list:
                problems.append(f"{condition_id}: evidence_refs must be a list")
                continue
            if status == "passed" and not references:
                problems.append(f"{condition_id}: passed condition has no evidence")
            for reference in references:
                state = evidence_status(reference)
                if state is None:
                    problems.append(f"{condition_id}: evidence {reference} does not exist")
                elif state != "valid":
                    problems.append(f"{condition_id}: evidence {reference} is {state}")
        required = extensions.get("required_evidence", [])
        if type(required) is not list:
            problems.append("required_evidence must be a list")
            required = []
        for requirement in required:
            if type(requirement) is not dict:
                problems.append("required evidence entry is not an object")
                continue
            label = requirement.get("subject") or requirement.get("kind") or "unnamed requirement"
            references = requirement.get("evidence_refs")
            if type(references) is list and references:
                for reference in references:
                    state = evidence_status(reference)
                    if state is None:
                        problems.append(f"required evidence {label}: {reference} does not exist")
                    elif state != "valid":
                        problems.append(f"required evidence {label}: {reference} is {state}")
                continue
            kind = requirement.get("kind")
            subject = requirement.get("subject")
            matched = [
                item for item in evidence.values()
                if evidence_status(item["id"]) == "valid"
                and (kind is None or item["kind"] == kind)
                and (subject is None or item["subject"] == subject)
            ]
            if not matched:
                problems.append(f"required evidence missing: {label}")
        risk = extensions.get("risk_level")
        if risk in {"high", "critical"}:
            reviews = [
                item for item in evidence.values()
                if item["kind"] == "review" and evidence_status(item["id"]) == "valid"
            ]
            if not reviews:
                problems.append("high-risk goal lacks a valid independent review")
            else:
                implementer = extensions.get("implementer") or extensions.get("owner")
                if type(implementer) is str and implementer.strip():
                    review_ids = {item["id"] for item in reviews}
                    independent = False
                    for review in connection.execute("SELECT * FROM reviews"):
                        references = _decode_json(review["evidence_refs"], "review evidence refs")
                        if (
                            review["verdict"] == "go"
                            and type(review["reviewer"]) is str
                            and review["reviewer"].strip()
                            and review["reviewer"] != implementer
                            and type(references) is list
                            and review_ids.intersection(references)
                        ):
                            independent = True
                            break
                    if not independent:
                        problems.append("high-risk goal review does not name an independent reviewer")
        return problems

    @staticmethod
    def _stale_reasons(root: Path | None, evidence: dict) -> list[str]:
        """Reasons the recorded evidence no longer matches the worktree bytes."""
        if root is None:
            return []
        verdict = Store.evidence_applicability(root, evidence)
        if verdict["applicability"] != "stale":
            return []
        return list(verdict["reasons"])

    @staticmethod
    def _document_drift_problems(connection, root: Path | None) -> list[str]:
        """Re-evaluate every record ``doc_ref`` and fail closed on drift.

        A ``doc_ref`` records the hash of the long-form document at write time. Once
        the referenced bytes change, the structured record no longer faithfully
        describes its document, so any completion gate must block until the record is
        refreshed. Reporting the drift only in ``validate`` is not enough: the same
        check has to reach the evidence and completion gates.
        """
        if root is None:
            return []
        problems: list[str] = []
        rows = connection.execute(
            "SELECT kind, id, payload FROM records ORDER BY kind, id"
        ).fetchall()
        for row in rows:
            payload = _decode_json(row["payload"], "record payload")
            for issue in _doc_ref_issues(root, payload):
                problems.append(
                    f"record {row['kind']}/{row['id']} {issue['reference']}: {issue['reason']}"
                )
        return problems

    @staticmethod
    def _task_completion_problems(connection, task: dict, root: Path | None = None) -> list[str]:
        extensions = task.get("extensions")
        if type(extensions) is not dict:
            extensions = {}
        problems: list[str] = Store._document_drift_problems(connection, root)
        valid = []
        for row in Store._evidence_covers_task(connection, task["id"]):
            if row["status"] != "valid":
                continue
            stale = Store._stale_reasons(root, Store._evidence(row))
            if stale:
                # A covered artifact changed after verification: the evidence is
                # stale whether or not anyone refreshed the stored status yet.
                problems.append(
                    f"evidence {row['id']} covering task {task['id']} is stale: "
                    + "; ".join(stale)
                )
                continue
            valid.append(row)
        if not valid:
            problems.append(f"no valid evidence covers task {task['id']}")
        risk = extensions.get("risk")
        verification = extensions.get("verification")
        level = verification.get("level") if type(verification) is dict else None
        if risk in {"high", "critical"} or (type(level) is int and level >= 3):
            reviews = [
                dict(row) for row in connection.execute(
                    "SELECT * FROM reviews WHERE task_id = ? ORDER BY created_sequence DESC",
                    (task["id"],),
                )
            ]
            if not reviews:
                problems.append(f"high-risk task {task['id']} lacks an independent review")
            else:
                implementer = extensions.get("implementer") or extensions.get("owner")
                if type(implementer) is not str or not implementer.strip():
                    # Without a recorded implementer, reviewer independence cannot be
                    # established; fail closed instead of accepting any reviewer.
                    problems.append(
                        f"high-risk task {task['id']} has no recorded implementer, "
                        "so reviewer independence cannot be established"
                    )
                    accepted = []
                else:
                    accepted = [
                        review for review in reviews
                        if review["verdict"] == "go" and review["reviewer"] != implementer
                    ]
                if not accepted:
                    problems.append(
                        f"high-risk task {task['id']} lacks a go review from an independent reviewer"
                    )
                else:
                    bound = []
                    for review in accepted:
                        references = _decode_json(review["evidence_refs"], "review evidence refs")
                        for reference in references:
                            row = connection.execute(
                                "SELECT * FROM evidence WHERE id = ?", (reference,)
                            ).fetchone()
                            if row is None or row["status"] != "valid":
                                continue
                            if Store._stale_reasons(root, Store._evidence(row)):
                                continue
                            bound.append(review)
                            break
                    if not bound:
                        problems.append(
                            f"high-risk task {task['id']} has no go review bound to current evidence "
                            "(review evidence_refs must name valid, non-stale evidence)"
                        )
        return problems

    def _transition(self, connection, action: str, payload: dict, sequence: int) -> dict:
        if action == "goal.create":
            connection.execute(
                "INSERT INTO goals VALUES (?, ?, 'active', ?, ?, ?)",
                (payload["id"], payload["title"], _json(payload.get("extensions", {})), sequence, sequence),
            )
            return {"goal_id": payload["id"], "status": "active"}
        if action == "goal.update":
            row = connection.execute(
                "SELECT * FROM goals WHERE id = ?", (payload["id"],)
            ).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown goal: {payload['id']}")
            extensions = _decode_json(row["extensions"], "goal extensions")
            if type(extensions) is not dict:
                extensions = {}
            for key in ("success_conditions", "required_evidence"):
                if key in payload:
                    # Only the fields that legitimately accrue evidence over the
                    # goal's life may change; risk_level stays frozen so this
                    # action cannot drop the independent-review requirement.
                    extensions[key] = payload[key]
            connection.execute(
                "UPDATE goals SET extensions = ?, updated_sequence = ? WHERE id = ?",
                (_json(extensions), sequence, payload["id"]),
            )
            return {"goal_id": payload["id"], "updated": True}
        if action == "goal.complete":
            row = connection.execute("SELECT * FROM goals WHERE id = ?", (payload["id"],)).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown goal: {payload['id']}")
            if row["status"] != "active":
                raise StateError("state_conflict", f"Cannot complete a {row['status']} goal")
            problems = self._goal_completion_problems(connection, payload["id"], self.root)
            if problems:
                raise StateError("goal_gate", "Goal completion rejected: " + "; ".join(problems))
            connection.execute(
                "UPDATE goals SET status = 'complete', updated_sequence = ? WHERE id = ?",
                (sequence, payload["id"]),
            )
            return {"goal_id": payload["id"], "status": "complete"}
        if action == "task.create":
            self._active_goal(connection, payload["goal_id"])
            connection.execute(
                """INSERT INTO tasks (id, title, goal_id, status, extensions, created_sequence, updated_sequence)
                   VALUES (?, ?, ?, 'ready', ?, ?, ?)""",
                (payload["id"], payload["title"], payload["goal_id"],
                 _json(payload.get("extensions", {})), sequence, sequence),
            )
            return {"task_id": payload["id"], "run_id": None, "status": "ready"}
        if action == "record.create":
            kind = payload["kind"]
            record_id = payload["id"]
            if connection.execute(
                "SELECT 1 FROM records WHERE kind = ? AND id = ?", (kind, record_id)
            ).fetchone():
                raise StateError("state_conflict", f"Record already exists: {kind}/{record_id}")
            record_payload = payload.get("payload", {})
            _record_governance(kind, record_payload)
            connection.execute(
                """INSERT INTO records
                   (kind, id, title, status, revision, payload, created_sequence, updated_sequence)
                   VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
                (kind, record_id, payload["title"], payload["status"],
                 _record_payload(record_payload), sequence, sequence),
            )
            return {
                "record_kind": kind, "record_id": record_id,
                "status": payload["status"], "revision": 1,
            }
        if action == "record.update":
            kind = payload["kind"]
            record_id = payload["id"]
            row = connection.execute(
                "SELECT * FROM records WHERE kind = ? AND id = ?", (kind, record_id)
            ).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown record: {kind}/{record_id}")
            if row["revision"] != payload["expected_record_revision"]:
                raise StateError(
                    "state_conflict",
                    f"Record revision is {row['revision']}; expected {payload['expected_record_revision']}",
                )
            record_payload = _decode_json(row["payload"], "record payload")
            if type(record_payload) is not dict:
                raise StateError("state_conflict", "Stored record payload is not an object")
            if "payload" in payload:
                record_payload.update(payload["payload"])
            status = payload.get("status", row["status"])
            _record_kind_status(kind, status)
            _record_governance(kind, record_payload)
            revision = row["revision"] + 1
            connection.execute(
                """UPDATE records SET status = ?, revision = ?, payload = ?, updated_sequence = ?
                   WHERE kind = ? AND id = ?""",
                (status, revision, _record_payload(record_payload), sequence, kind, record_id),
            )
            return {
                "record_kind": kind, "record_id": record_id,
                "status": status, "revision": revision,
            }
        if action == "record.link":
            for kind_key, id_key in (("from_kind", "from_id"), ("to_kind", "to_id")):
                if connection.execute(
                    "SELECT 1 FROM records WHERE kind = ? AND id = ?",
                    (payload[kind_key], payload[id_key]),
                ).fetchone() is None:
                    raise StateError(
                        "not_found",
                        f"Unknown record: {payload[kind_key]}/{payload[id_key]}",
                    )
            if connection.execute(
                """SELECT 1 FROM record_links
                   WHERE from_kind = ? AND from_id = ? AND relation = ?
                     AND to_kind = ? AND to_id = ?""",
                (payload["from_kind"], payload["from_id"], payload["relation"],
                 payload["to_kind"], payload["to_id"]),
            ).fetchone():
                raise StateError("state_conflict", "Record link already exists")
            connection.execute(
                """INSERT INTO record_links
                   (from_kind, from_id, relation, to_kind, to_id, created_sequence)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (payload["from_kind"], payload["from_id"], payload["relation"],
                 payload["to_kind"], payload["to_id"], sequence),
            )
            return {
                "from_kind": payload["from_kind"], "from_id": payload["from_id"],
                "relation": payload["relation"], "to_kind": payload["to_kind"],
                "to_id": payload["to_id"],
            }
        if action == "evidence.record":
            evidence_id = payload["id"]
            if connection.execute("SELECT 1 FROM evidence WHERE id = ?", (evidence_id,)).fetchone():
                raise StateError("state_conflict", f"Evidence already exists: {evidence_id}")
            task_id = payload.get("task_id")
            if task_id is not None and connection.execute(
                "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
            ).fetchone() is None:
                raise StateError("not_found", f"Unknown task: {task_id}")
            connection.execute(
                """INSERT INTO evidence
                   (id, task_id, kind, subject, status, covers, version_binding, recorded_sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (evidence_id, task_id, payload["kind"], payload["subject"], payload["status"],
                 _evidence_covers(payload.get("covers")), _version_binding(payload.get("version_binding")),
                 sequence),
            )
            return {"evidence_id": evidence_id, "status": payload["status"]}
        if action == "evidence.invalidate":
            row = connection.execute(
                "SELECT * FROM evidence WHERE id = ?", (payload["id"],)
            ).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown evidence: {payload['id']}")
            if row["invalidated_sequence"] is not None:
                raise StateError("state_conflict", f"Evidence is already invalidated: {payload['id']}")
            connection.execute(
                """UPDATE evidence SET status = 'stale', invalidated_sequence = ?,
                   invalidation_reason = ? WHERE id = ?""",
                (sequence, payload["reason"], payload["id"]),
            )
            return {"evidence_id": payload["id"], "status": "stale", "reason": payload["reason"]}
        if action == "review.record":
            if connection.execute("SELECT 1 FROM reviews WHERE id = ?", (payload["id"],)).fetchone():
                raise StateError("state_conflict", f"Review already exists: {payload['id']}")
            if connection.execute("SELECT 1 FROM tasks WHERE id = ?", (payload["task_id"],)).fetchone() is None:
                raise StateError("not_found", f"Unknown task: {payload['task_id']}")
            for evidence_id in payload["evidence_refs"]:
                if connection.execute("SELECT 1 FROM evidence WHERE id = ?", (evidence_id,)).fetchone() is None:
                    raise StateError("not_found", f"Unknown evidence reference: {evidence_id}")
            connection.execute(
                """INSERT INTO reviews
                   (id, task_id, reviewer, verdict, scope, evidence_refs, created_sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["id"], payload["task_id"], payload["reviewer"], payload["verdict"],
                 _json(payload["scope"]), _evidence_refs(payload["evidence_refs"]), sequence),
            )
            return {
                "review_id": payload["id"], "task_id": payload["task_id"],
                "verdict": payload["verdict"],
            }
        if action == "task.update":
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (payload["task_id"],)
            ).fetchone()
            if row is None:
                raise StateError("not_found", f"Unknown task: {payload['task_id']}")
            extensions = _decode_json(row["extensions"], "task extensions")
            if type(extensions) is not dict:
                extensions = {}
            for key in ("implementer", "owner"):
                if key in payload:
                    # Only attribution is mutable here: risk, evidence and gate
                    # fields stay frozen so this action cannot loosen a gate.
                    extensions[key] = payload[key].strip()
            connection.execute(
                "UPDATE tasks SET extensions = ?, updated_sequence = ? WHERE id = ?",
                (_json(extensions), sequence, payload["task_id"]),
            )
            return {"task_id": payload["task_id"], "updated": True}
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
            problems = self._task_completion_problems(connection, task, self.root)
            if problems:
                raise StateError("task_gate", "Task completion rejected: " + "; ".join(problems))
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
                "records": [dict(row) for row in connection.execute(
                    "SELECT * FROM records ORDER BY kind, id")],
                "record_links": [dict(row) for row in connection.execute(
                    "SELECT * FROM record_links ORDER BY from_kind, from_id, relation, to_kind, to_id")],
                "evidence": [dict(row) for row in connection.execute(
                    "SELECT * FROM evidence ORDER BY id")],
                "reviews": [dict(row) for row in connection.execute(
                    "SELECT * FROM reviews ORDER BY id")],
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
            "records": [dict(row) for row in connection.execute(
                "SELECT * FROM records ORDER BY kind, id")],
            "record_links": [dict(row) for row in connection.execute(
                "SELECT * FROM record_links ORDER BY from_kind, from_id, relation, to_kind, to_id")],
            "evidence": [dict(row) for row in connection.execute(
                "SELECT * FROM evidence ORDER BY id")],
            "reviews": [dict(row) for row in connection.execute(
                "SELECT * FROM reviews ORDER BY id")],
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
        records = []
        for row in entities["records"]:
            row = dict(row)
            row["created_sequence"] = remap(row["created_sequence"], "records")
            row["updated_sequence"] = remap(row["updated_sequence"], "records")
            records.append(row)
        translated["records"] = records
        links = []
        for row in entities["record_links"]:
            row = dict(row)
            row["created_sequence"] = remap(row["created_sequence"], "record_links")
            links.append(row)
        translated["record_links"] = links
        evidence = []
        for row in entities["evidence"]:
            row = dict(row)
            row["recorded_sequence"] = remap(row["recorded_sequence"], "evidence")
            row["invalidated_sequence"] = remap(row["invalidated_sequence"], "evidence")
            evidence.append(row)
        translated["evidence"] = evidence
        reviews = []
        for row in entities["reviews"]:
            row = dict(row)
            row["created_sequence"] = remap(row["created_sequence"], "reviews")
            reviews.append(row)
        translated["reviews"] = reviews
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
            connection.execute("DELETE FROM reviews")
            connection.execute("DELETE FROM evidence")
            connection.execute("DELETE FROM record_links")
            connection.execute("DELETE FROM records")
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
            for row in translated["records"]:
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["records"]))
            for row in translated["record_links"]:
                connection.execute(
                    "INSERT INTO record_links VALUES (?, ?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["record_links"]))
            for row in translated["evidence"]:
                connection.execute(
                    "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["evidence"]))
            for row in translated["reviews"]:
                connection.execute(
                    "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?)",
                    tuple(row[column] for column in _BUNDLE_COLUMNS["reviews"]))
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
        return [
            f"record {item['kind']}/{item['id']} {item['reference']}: {item['reason']}"
            for item in self.stale_documents()
        ]

    def _verify_ledger(self, connection) -> list[str]:
        """Replay the ledger against the entity tables on one connection.

        Shared by the read-only audit and by import validation, so a snapshot
        can never be accepted into a store that then fails its own audit.
        """
        metadata = self._metadata(connection)
        problems: list[str] = []
        run_links = {row["id"]: row["run_id"] for row in connection.execute("SELECT id, run_id FROM tasks")}
        created_goals: set[str] = set()
        goal_statuses: dict[str, str] = {}
        created_tasks: set[str] = set()
        begun_runs: dict[str, str] = {}
        waited: list[tuple[str, str]] = []
        records: dict[tuple[str, str], dict] = {}
        links: set[tuple[str, str, str, str, str]] = set()
        evidence: dict[str, dict] = {}
        reviews: dict[str, dict] = {}
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
                    if action == "goal.create":
                        run_id = None
                        result = {"goal_id": payload["id"], "status": "active"}
                        created_goals.add(payload["id"])
                        goal_statuses[payload["id"]] = "active"
                    elif action == "goal.complete":
                        run_id = None
                        if payload["id"] not in created_goals:
                            raise ValueError("Goal completion references an unknown goal")
                        goal_statuses[payload["id"]] = "complete"
                        result = {"goal_id": payload["id"], "status": "complete"}
                    elif action == "goal.update":
                        run_id = None
                        if payload["id"] not in created_goals:
                            raise ValueError("Goal update references an unknown goal")
                        result = {"goal_id": payload["id"], "updated": True}
                    elif action == "task.create":
                        task_id = payload["id"]
                        run_id = None
                        created_tasks.add(task_id)
                        result = {"task_id": task_id, "run_id": None, "status": "ready"}
                    elif action == "task.update":
                        task_id = payload["task_id"]
                        run_id = None
                        if task_id not in created_tasks:
                            raise ValueError("Task update references an unknown task")
                        result = {"task_id": task_id, "updated": True}
                    elif action in {
                        "task.begin", "task.resume", "task.wait", "task.handoff",
                        "task.finish", "task.cancel",
                    }:
                        task_id = payload["task_id"]
                        status = {
                            "task.begin": "in-progress", "task.resume": "in-progress",
                            "task.wait": "waiting-user" if payload.get("kind") == "user" else "blocked",
                            "task.handoff": "handed-off", "task.finish": "implemented-unverified",
                            "task.cancel": "cancelled",
                        }[action]
                        if task_id in run_links:
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
                    elif action == "record.create":
                        key = (payload["kind"], payload["id"])
                        if key in records:
                            raise ValueError("Duplicate record create in ledger")
                        records[key] = {
                            "title": payload["title"], "status": payload["status"],
                            "revision": 1, "created_sequence": row["local_sequence"],
                            "updated_sequence": row["local_sequence"],
                        }
                        result = {
                            "record_kind": key[0], "record_id": key[1],
                            "status": payload["status"], "revision": 1,
                        }
                    elif action == "record.update":
                        key = (payload["kind"], payload["id"])
                        state = records.get(key)
                        if state is None:
                            raise ValueError("Record update references an unknown record")
                        if state["revision"] != payload["expected_record_revision"]:
                            raise ValueError("Record update revision mismatch in ledger")
                        status = payload.get("status", state["status"])
                        state.update({
                            "status": status, "revision": state["revision"] + 1,
                            "updated_sequence": row["local_sequence"],
                        })
                        result = {
                            "record_kind": key[0], "record_id": key[1],
                            "status": status, "revision": state["revision"],
                        }
                    elif action == "record.link":
                        key = (
                            payload["from_kind"], payload["from_id"], payload["relation"],
                            payload["to_kind"], payload["to_id"],
                        )
                        if key in links:
                            raise ValueError("Duplicate record link in ledger")
                        links.add(key)
                        result = {
                            "from_kind": payload["from_kind"], "from_id": payload["from_id"],
                            "relation": payload["relation"], "to_kind": payload["to_kind"],
                            "to_id": payload["to_id"],
                        }
                    elif action == "evidence.record":
                        if payload["id"] in evidence:
                            raise ValueError("Duplicate evidence record in ledger")
                        evidence[payload["id"]] = {
                            "task_id": payload.get("task_id"), "status": payload["status"],
                            "recorded_sequence": row["local_sequence"],
                            "invalidated_sequence": None, "invalidation_reason": None,
                        }
                        result = {"evidence_id": payload["id"], "status": payload["status"]}
                    elif action == "evidence.invalidate":
                        state = evidence.get(payload["id"])
                        if state is None or state["invalidated_sequence"] is not None:
                            raise ValueError("Evidence invalidation references an unknown or invalidated record")
                        state.update({
                            "status": "stale",
                            "invalidated_sequence": row["local_sequence"],
                            "invalidation_reason": payload["reason"],
                        })
                        result = {
                            "evidence_id": payload["id"], "status": "stale",
                            "reason": payload["reason"],
                        }
                    elif action == "review.record":
                        if payload["id"] in reviews:
                            raise ValueError("Duplicate review record in ledger")
                        reviews[payload["id"]] = {
                            "task_id": payload["task_id"], "verdict": payload["verdict"],
                            "created_sequence": row["local_sequence"],
                        }
                        result = {
                            "review_id": payload["id"], "task_id": payload["task_id"],
                            "verdict": payload["verdict"],
                        }
                    else:
                        raise ValueError(f"Unknown ledger action: {action}")
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
        stored_goal_statuses = {
            row["id"]: row["status"] for row in connection.execute("SELECT id, status FROM goals")
        }
        tasks = {row["id"] for row in connection.execute("SELECT id FROM tasks")}
        runs = {row["id"]: row["task_id"] for row in connection.execute("SELECT id, task_id FROM runs")}
        blockers = sorted(
            (row["task_id"], row["kind"]) for row in connection.execute("SELECT task_id, kind FROM blockers")
        )
        stored_records = {
            (row["kind"], row["id"]): {
                "title": row["title"], "status": row["status"], "revision": row["revision"],
                "created_sequence": row["created_sequence"], "updated_sequence": row["updated_sequence"],
            }
            for row in connection.execute("SELECT * FROM records")
        }
        stored_links = {
            (row["from_kind"], row["from_id"], row["relation"], row["to_kind"], row["to_id"])
            for row in connection.execute("SELECT * FROM record_links")
        }
        stored_evidence = {
            row["id"]: {
                "task_id": row["task_id"], "status": row["status"],
                "recorded_sequence": row["recorded_sequence"],
                "invalidated_sequence": row["invalidated_sequence"],
                "invalidation_reason": row["invalidation_reason"],
            }
            for row in connection.execute("SELECT * FROM evidence")
        }
        stored_reviews = {
            row["id"]: {
                "task_id": row["task_id"], "verdict": row["verdict"],
                "created_sequence": row["created_sequence"],
            }
            for row in connection.execute("SELECT * FROM reviews")
        }
        if goals != created_goals:
            problems.append("Ledger and entity tables disagree on goals")
        if goal_statuses != stored_goal_statuses:
            problems.append("Ledger and entity tables disagree on goal statuses")
        if tasks != created_tasks:
            problems.append("Ledger and entity tables disagree on tasks")
        if runs != begun_runs:
            problems.append("Ledger and entity tables disagree on runs")
        if blockers != sorted(waited):
            problems.append("Ledger and entity tables disagree on blockers")
        if records != stored_records:
            problems.append("Ledger and entity tables disagree on records")
        if links != stored_links:
            problems.append("Ledger and entity tables disagree on record links")
        if evidence != stored_evidence:
            problems.append("Ledger and entity tables disagree on evidence")
        if reviews != stored_reviews:
            problems.append("Ledger and entity tables disagree on reviews")
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
            if connection.execute(
                """SELECT 1 FROM records WHERE created_sequence < 1
                   OR updated_sequence < created_sequence OR updated_sequence > ? LIMIT 1""",
                (metadata["local_revision"],),
            ).fetchone():
                raise StateError("state_conflict", "Invalid record sequence bounds")
            if connection.execute(
                """SELECT 1 FROM record_links WHERE created_sequence < 1
                   OR created_sequence > ? LIMIT 1""",
                (metadata["local_revision"],),
            ).fetchone():
                raise StateError("state_conflict", "Invalid record link sequence bounds")
            if connection.execute(
                """SELECT 1 FROM evidence WHERE recorded_sequence < 1
                   OR recorded_sequence > ? OR invalidated_sequence < recorded_sequence
                   OR invalidated_sequence > ? LIMIT 1""",
                (metadata["local_revision"], metadata["local_revision"]),
            ).fetchone():
                raise StateError("state_conflict", "Invalid evidence sequence bounds")
            if connection.execute(
                """SELECT 1 FROM reviews WHERE created_sequence < 1
                   OR created_sequence > ? LIMIT 1""",
                (metadata["local_revision"],),
            ).fetchone():
                raise StateError("state_conflict", "Invalid review sequence bounds")
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
