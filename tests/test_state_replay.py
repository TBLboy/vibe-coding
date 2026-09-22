"""TASK-048: the ledger must deterministically rebuild the SQLite projection.

The golden test is the migration safety net: whatever a future Format 3 writer
emits, replaying it from an empty store has to reproduce the same entities the
live store holds, and a single tampered command has to break that equality.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import initialize  # noqa: E402
from state_replay import logical_state_hash, reduce_ledger  # noqa: E402


TABLES = (
    "goals", "tasks", "runs", "blockers", "records",
    "record_links", "evidence", "reviews",
)


class GoldenReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = initialize(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def apply(self, action: str, payload: dict) -> dict:
        return self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": self.store.status()["revision"],
            "action": action, "payload": payload,
        })

    def build_ledger(self) -> None:
        """Exercise every ledger action so replay covers the whole surface."""
        self.apply("goal.create", {
            "id": "GOAL-001", "title": "Ship format 3",
            "extensions": {"risk_level": "normal"},
        })
        self.apply("goal.update", {
            "id": "GOAL-001",
            "success_conditions": [
                {"id": "SC-1", "status": "passed", "evidence_refs": ["EVID-001"]},
            ],
        })
        self.apply("task.create", {
            "id": "TASK-001", "title": "Implement replay", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal"},
        })
        self.apply("task.update", {"task_id": "TASK-001", "implementer": "codex"})
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "write reducer",
        })
        self.apply("task.wait", {
            "task_id": "TASK-001", "kind": "user", "reason": "await approval",
            "question_ref": "Q-1", "resume_when": "user approves",
        })
        self.apply("task.resume", {"task_id": "TASK-001", "next_action": "finish reducer"})
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
            "version_binding": {"git_commit": "abc123"},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "reviewer",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        self.apply("task.finish", {"task_id": "TASK-001", "summary": "reducer landed"})
        self.apply("task.create", {"id": "TASK-002", "title": "Second", "goal_id": "GOAL-001"})
        self.apply("task.begin", {
            "task_id": "TASK-002", "run_id": "RUN-002", "next_action": "handoff",
        })
        self.apply("task.handoff", {"task_id": "TASK-002", "next_action": "resume later"})
        self.apply("task.cancel", {"task_id": "TASK-002", "reason": "superseded"})
        self.apply("task.create", {"id": "TASK-003", "title": "Third", "goal_id": "GOAL-001"})
        self.apply("task.begin", {
            "task_id": "TASK-003", "run_id": "RUN-003", "next_action": "wait",
        })
        self.apply("task.wait", {
            "task_id": "TASK-003", "kind": "dependency", "reason": "blocked upstream",
            "resume_when": "dependency lands",
        })
        self.apply("task.cancel", {"task_id": "TASK-003", "reason": "scope dropped"})
        self.apply("record.create", {
            "kind": "research", "id": "RES-001", "title": "Replay research",
            "status": "draft", "payload": {"summary": "ledger is source of truth"},
        })
        self.apply("record.update", {
            "kind": "research", "id": "RES-001", "expected_record_revision": 1,
            "status": "complete", "payload": {"summary": "ledger is the source of truth"},
        })
        self.apply("record.create", {
            "kind": "decision", "id": "DEC-001", "title": "Replay decision",
            "status": "active", "payload": {"summary": "share one reducer"},
        })
        self.apply("record.link", {
            "from_kind": "research", "from_id": "RES-001", "relation": "references",
            "to_kind": "decision", "to_id": "DEC-001",
        })
        self.apply("evidence.record", {
            "id": "EVID-002", "kind": "manual", "subject": "scratch",
            "status": "candidate",
        })
        self.apply("evidence.invalidate", {"id": "EVID-002", "reason": "superseded"})
        self.apply("goal.complete", {"id": "GOAL-001"})

    def ledger(self) -> list[dict]:
        with self.store._connection() as connection:
            return [
                {key: row[key] for key in row.keys()}
                for row in connection.execute(
                    "SELECT * FROM commands ORDER BY local_sequence"
                )
            ]

    def live_entities(self) -> dict:
        with self.store._connection() as connection:
            return self.store._entity_rows(connection)

    def test_replay_reconstructs_every_table_from_the_ledger(self) -> None:
        self.build_ledger()
        entries = self.ledger()
        self.assertEqual(len(entries), self.store.status()["revision"])

        reduced = reduce_ledger(entries)
        live = self.live_entities()

        for table in TABLES:
            self.assertEqual(reduced[table], live[table], f"table {table} diverged")

    def test_replay_from_a_fresh_store_matches_the_original(self) -> None:
        self.build_ledger()
        entries = self.ledger()
        original = self.live_entities()

        replay_root = self.root / "replay"
        replay_root.mkdir()
        replayed = initialize(replay_root)
        for entry in entries:
            replayed.apply(json.loads(entry["request_json"]))

        with replayed._connection() as connection:
            rebuilt = replayed._entity_rows(connection)

        self.assertEqual(rebuilt, original)

    def test_logical_state_hash_is_stable_and_reproducible(self) -> None:
        self.build_ledger()
        entries = self.ledger()
        first = reduce_ledger(entries)
        second = reduce_ledger(copy.deepcopy(entries))

        self.assertEqual(first, second)
        self.assertEqual(logical_state_hash(first), logical_state_hash(second))
        self.assertEqual(len(logical_state_hash(first)), 64)

    def test_tampered_command_breaks_the_golden_replay(self) -> None:
        self.build_ledger()
        entries = self.ledger()
        live = self.live_entities()
        baseline = logical_state_hash(reduce_ledger(entries))

        tampered = copy.deepcopy(entries)
        victim = next(
            entry for entry in tampered
            if json.loads(entry["request_json"])["action"] == "task.create"
        )
        request = json.loads(victim["request_json"])
        request["payload"]["title"] = "Tampered title"
        victim["request_json"] = json.dumps(request, sort_keys=True, separators=(",", ":"))

        broken = reduce_ledger(tampered)

        self.assertNotEqual(broken["tasks"], live["tasks"])
        self.assertNotEqual(logical_state_hash(broken), baseline)

    def test_verify_ledger_detects_direct_sqlite_tampering(self) -> None:
        self.build_ledger()
        connection = sqlite3.connect(self.store.path)
        connection.execute(
            "UPDATE tasks SET title = 'forged' WHERE id = 'TASK-001'"
        )
        connection.commit()
        connection.close()

        problems = self.store.validate()
        self.assertTrue(
            any("disagree on tasks" in problem for problem in problems), problems
        )


if __name__ == "__main__":
    unittest.main()
