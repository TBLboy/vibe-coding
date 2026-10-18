"""V3 PR-06 / T29: a failed store upgrade leaves the old ledger and SQLite readable.

Release gate §10: the old state store must be migratable, and any error must be
recoverable to a readable pre-upgrade state; the new version's `ledger verify`,
`validate` and snapshot round-trips must pass without changing historical event hashes.

The upgrade is a projection-only rebuild (the ledger is the fact source), so a refusal
must be exactly that: a refusal. These tests pin that nothing is half-written and that
the ledger bytes are untouched when the migration cannot proceed.
"""
from __future__ import annotations

import sqlite3
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import _DDL, _json, _request, StateError, Store  # noqa: E402
from state_context import initialize, open_store  # noqa: E402
from state_replay import reduce_ledger  # noqa: E402


def write_schema_three_store(path: Path, project_id: str, context_id: str) -> None:
    """Write the projection exactly as store schema 3 defined it.

    This is a *minimal* hand-built projection, not a replayed ledger, so the tests here
    assert migration outcomes (rows preserved, idempotent, widened CHECK usable) rather
    than `validate() == []`. Full ledger/receipt equivalence is covered by
    test_state_replay.py.
    """
    old_ddl = [
        statement
        .replace("CHECK(store_schema = 5)", "CHECK(store_schema = 3)")
        .replace("'complete','cancelled'", "'complete'")
        for statement in _DDL
    ]
    envelope = {
        "schema_version": 1, "command_id": "cmd-1", "expected_revision": 0,
        "action": "goal.create", "payload": {"id": "GOAL-001", "title": "Goal"},
    }
    _, canonical, request_hash = _request(envelope)
    receipt = _json({
        "command_id": "cmd-1", "local_sequence": 1, "revision": 1,
        "action": "goal.create", "result": {"goal_id": "GOAL-001", "status": "active"},
    })
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        for statement in old_ddl:
            connection.execute(statement)
        connection.execute("INSERT INTO metadata VALUES (1, 3, 1, ?, ?, 1)",
                           (project_id, context_id))
        connection.execute("INSERT INTO projection_jobs VALUES (1, 1)")
        connection.execute(
            "INSERT INTO exchange VALUES (1, NULL, 0, NULL, NULL, NULL, NULL)")
        connection.execute(
            "INSERT INTO goals VALUES ('GOAL-001', 'Goal', 'active', '{}', 1, 1)")
        # A store with a row must also carry the command and event that produced it,
        # otherwise the revision/receipt/event cardinality check is violated.
        connection.execute(
            """INSERT INTO commands (command_id, local_sequence, origin_kind,
                   origin_context_id, origin_revision, action, request_json,
                   request_hash, receipt_json, created_at)
               VALUES ('cmd-1', 1, 'local', ?, 0, 'goal.create', ?, ?, ?,
                       '2026-01-01T00:00:00Z')""",
            (context_id, canonical, request_hash, receipt),
        )
        connection.execute(
            """INSERT INTO events (local_sequence, command_id, origin_kind, origin_context_id,
                   origin_revision, action, request_hash, created_at)
               VALUES (1, 'cmd-1', 'local', ?, 0, 'goal.create', ?, '2026-01-01T00:00:00Z')""",
            (context_id, request_hash),
        )
        connection.commit()
    finally:
        connection.close()


def write_schema_four_run_store(path: Path, project_id: str, context_id: str) -> None:
    """Write a genuine v4-shaped projection with one formerly global active Run."""
    old_ddl = []
    for statement in _DDL:
        statement = statement.replace("CHECK(store_schema = 5)", "CHECK(store_schema = 4)")
        if statement.startswith("CREATE TABLE runs"):
            statement = """CREATE TABLE runs (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
                status TEXT NOT NULL CHECK(status IN ('active','waiting-user','blocked','handed-off','finished','cancelled')),
                created_sequence INTEGER NOT NULL, updated_sequence INTEGER NOT NULL)"""
        old_ddl.append(statement)
    old_ddl.append("CREATE UNIQUE INDEX one_active_run ON runs(status) WHERE status = 'active'")
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        for statement in old_ddl:
            connection.execute(statement)
        connection.execute("INSERT INTO metadata VALUES (1, 4, 1, ?, ?, 3)", (project_id, context_id))
        connection.execute("INSERT INTO projection_jobs VALUES (1, 3)")
        connection.execute("INSERT INTO exchange VALUES (1, NULL, 0, NULL, NULL, NULL, NULL)")
        connection.execute("INSERT INTO goals VALUES ('GOAL-001', 'Goal', 'active', '{}', 1, 1)")
        connection.execute(
            """INSERT INTO tasks VALUES ('TASK-001', 'Task', 'GOAL-001', 'in-progress',
               'RUN-001', 'continue', NULL, NULL, '{}', 2, 3)"""
        )
        connection.execute("INSERT INTO runs VALUES ('RUN-001', 'TASK-001', 'active', 3, 3)")
        connection.commit()
    finally:
        connection.close()


def report_unknown_store_schema(path: Path, version: int = 99) -> None:
    """Rewrite metadata so the store claims a version this build does not know.

    The CHECK constraint is what stops a *writer* from producing this state; a store
    written by a newer build has no such constraint, so the test writes it directly
    rather than pretending the constraint would allow it.
    """
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("ALTER TABLE metadata RENAME TO metadata_old")
        connection.execute(
            """CREATE TABLE metadata (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                store_schema INTEGER NOT NULL,
                schema_version INTEGER NOT NULL CHECK(schema_version = 1),
                project_id TEXT NOT NULL, context_id TEXT NOT NULL,
                local_revision INTEGER NOT NULL CHECK(local_revision >= 0))"""
        )
        connection.execute(
            "INSERT INTO metadata SELECT singleton, ?, schema_version, project_id, "
            "context_id, local_revision FROM metadata_old",
            (version,),
        )
        connection.execute("DROP TABLE metadata_old")
        connection.commit()
    finally:
        connection.close()


def drop_store_metadata(path: Path) -> None:
    """Leave a store whose metadata row is gone: the other unrecoverable-by-guessing case."""
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("DELETE FROM metadata")
        connection.commit()
    finally:
        connection.close()


class UpgradeRecoveryTests(unittest.TestCase):
    def test_an_unknown_store_schema_is_refused_without_partial_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.sqlite3"
            project_id, context_id = uuid.uuid4().hex, "c" * 64
            write_schema_three_store(path, project_id, context_id)
            report_unknown_store_schema(path, 99)

            store = Store(path, project_id, context_id)
            with self.assertRaises(StateError) as caught:
                store.upgrade()
            self.assertEqual(caught.exception.code, "state_conflict")
            self.assertIn("99", str(caught.exception))

            # Still the readable store it was: same version, same rows, no stray tables.
            connection = sqlite3.connect(str(path))
            try:
                self.assertEqual(
                    connection.execute("SELECT store_schema FROM metadata").fetchone()[0], 99)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM goals").fetchone()[0], 1)
                self.assertEqual(
                    connection.execute("SELECT id FROM goals").fetchone()[0], "GOAL-001")
                tables = {
                    row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'")
                }
                self.assertNotIn("metadata_upgrade", tables, tables)
                self.assertNotIn("goals_upgrade", tables, tables)
            finally:
                connection.close()

    def test_missing_store_metadata_is_refused_instead_of_reinitialized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.sqlite3"
            project_id, context_id = uuid.uuid4().hex, "c" * 64
            write_schema_three_store(path, project_id, context_id)
            drop_store_metadata(path)

            store = Store(path, project_id, context_id)
            with self.assertRaises(StateError) as caught:
                store.upgrade()
            self.assertEqual(caught.exception.code, "state_conflict")
            # The rows are still there: a damaged marker must not silently become a
            # fresh store, and nothing may be deleted to make the error go away.
            connection = sqlite3.connect(str(path))
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM goals").fetchone()[0], 1)
            finally:
                connection.close()

    def test_a_schema_three_store_is_migrated_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.sqlite3"
            project_id, context_id = uuid.uuid4().hex, "c" * 64
            write_schema_three_store(path, project_id, context_id)

            store = Store(path, project_id, context_id)
            self.assertEqual(store.upgrade(), {"status": "upgraded", "store_schema": 5})
            # Idempotent: opening the same store again reports it is already current.
            self.assertEqual(store.upgrade(), {"status": "current", "store_schema": 5})
            self.assertEqual(store.get_goal("GOAL-001")["status"], "active")
            # The widened CHECK is live after the rebuild: a goal can now be cancelled.
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.cancel",
                "payload": {"id": "GOAL-001", "reason": "not needed"},
            })
            self.assertEqual(store.get_goal("GOAL-001")["status"], "cancelled")

    def test_schema_four_active_run_migrates_to_a_conservative_legacy_scope(self) -> None:
        """Old active work is not silently made concurrent when the global lock lifts."""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.sqlite3"
            project_id, context_id = uuid.uuid4().hex, "c" * 64
            write_schema_four_run_store(path, project_id, context_id)
            store = Store(path, project_id, context_id)
            self.assertEqual(store.upgrade(), {"status": "upgraded", "store_schema": 5})
            run = store.get_task("TASK-001")["run"]
            self.assertEqual(
                {key: run[key] for key in ("owner", "session_id", "write_scope")},
                {"owner": "legacy", "session_id": "legacy", "write_scope": '["."]'},
            )
            self.assertIsNone(
                sqlite3.connect(str(path)).execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'one_active_run'"
                ).fetchone()
            )

    def test_successful_schema_four_upgrade_preserves_project_ledger_bytes(self) -> None:
        """A projection migration is never allowed to rewrite the fact-source ledger."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = initialize(root)
            def apply(action, payload):
                return store.apply({
                    "schema_version": 1, "command_id": uuid.uuid4().hex,
                    "expected_revision": store.status()["revision"], "action": action, "payload": payload,
                })
            apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
            apply("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"})
            apply("task.begin", {
                "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "work",
                "owner": "agent", "session_id": "session", "write_scope": ["module"],
            })
            ledger = next(root.rglob("ledger.jsonl"))
            before = ledger.read_bytes()
            path, project_id, context_id = store.path, store.project_id, store.context_id
            del store
            # Downgrade only the projection shape/marker; leave the real ledger untouched.
            connection = sqlite3.connect(str(path))
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DROP INDEX IF EXISTS one_active_run")
            connection.execute("ALTER TABLE runs RENAME TO runs_v5")
            connection.execute("""CREATE TABLE runs (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
                status TEXT NOT NULL CHECK(status IN ('active','waiting-user','blocked','handed-off','finished','cancelled')),
                created_sequence INTEGER NOT NULL, updated_sequence INTEGER NOT NULL)""")
            connection.execute("INSERT INTO runs SELECT id, task_id, status, created_sequence, updated_sequence FROM runs_v5")
            connection.execute("DROP TABLE runs_v5")
            connection.execute("ALTER TABLE metadata RENAME TO metadata_v5")
            connection.execute("""CREATE TABLE metadata (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1), store_schema INTEGER NOT NULL CHECK(store_schema = 4),
                schema_version INTEGER NOT NULL CHECK(schema_version = 1), project_id TEXT NOT NULL,
                context_id TEXT NOT NULL, local_revision INTEGER NOT NULL CHECK(local_revision >= 0))""")
            connection.execute("INSERT INTO metadata SELECT singleton, 4, schema_version, project_id, context_id, local_revision FROM metadata_v5")
            connection.execute("DROP TABLE metadata_v5")
            connection.commit(); connection.close()
            upgraded = Store(path, project_id, context_id)
            self.assertEqual(upgraded.upgrade(), {"status": "upgraded", "store_schema": 5})
            self.assertEqual(ledger.read_bytes(), before)
            self.assertEqual(upgraded.upgrade(), {"status": "current", "store_schema": 5})

    def test_unbound_historic_begin_replays_as_a_conservative_legacy_binding(self) -> None:
        """Old ledger request bytes remain reducible after the v5 binding requirement."""
        entries = [
            {"local_sequence": 1, "request_json": _json({"schema_version": 1, "command_id": "c1", "expected_revision": 0, "action": "goal.create", "payload": {"id": "G", "title": "Goal"}})},
            {"local_sequence": 2, "request_json": _json({"schema_version": 1, "command_id": "c2", "expected_revision": 1, "action": "task.create", "payload": {"id": "T", "title": "Task", "goal_id": "G"}})},
            {"local_sequence": 3, "request_json": _json({"schema_version": 1, "command_id": "c3", "expected_revision": 2, "action": "task.begin", "payload": {"task_id": "T", "run_id": "R", "next_action": "old work"}})},
        ]
        state = reduce_ledger(entries)
        self.assertEqual(state["runs"][0]["write_scope"], '["."]')
        self.assertEqual(state["runs"][0]["owner"], "legacy")

    def test_a_refused_upgrade_leaves_the_ledger_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = initialize(root)
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": "goal.create", "payload": {"id": "GOAL-1", "title": "Goal"},
            })
            ledgers = sorted(root.rglob("ledger.jsonl"))
            self.assertTrue(ledgers, "the project must keep a ledger")
            before = {path: path.read_bytes() for path in ledgers}
            store_path = store.path
            del store

            report_unknown_store_schema(store_path, 99)

            with self.assertRaises(StateError) as caught:
                open_store(root)
            self.assertEqual(caught.exception.code, "state_conflict")

            # The ledger is the fact source and must be untouched by a refused upgrade.
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content, path)

            # And the projection is still readable with the row it had.
            connection = sqlite3.connect(str(store_path))
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM goals").fetchone()[0], 1)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
