"""TASK-049: export the command history to a Git-tracked Format 3 ledger."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import initialize  # noqa: E402
from state_ledger import (  # noqa: E402
    LEDGER_RELATIVE, export_ledger, ledger_path, read_ledger, render_ledger,
    verify_ledger,
)
from state_replay import logical_state_hash, reduce_ledger  # noqa: E402
from state_store import StateError  # noqa: E402


class LedgerExportTests(unittest.TestCase):
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

    def build(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "work",
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.apply("task.finish", {"task_id": "TASK-001", "summary": "done"})

    def commands(self) -> list[dict]:
        with self.store._connection() as connection:
            return [
                {key: row[key] for key in row.keys()}
                for row in connection.execute("SELECT * FROM commands ORDER BY local_sequence")
            ]

    def live(self) -> dict:
        with self.store._connection() as connection:
            return self.store._entity_rows(connection)

    def test_export_replays_back_to_the_live_store(self) -> None:
        self.build()
        result = export_ledger(self.store)

        self.assertEqual(result["events"], len(self.commands()))
        self.assertEqual(result["revision"], self.store.status()["revision"])
        path = self.root / LEDGER_RELATIVE
        self.assertTrue(path.is_file())

        entries = read_ledger(path)
        self.assertEqual(reduce_ledger(entries), self.live())

    def test_export_is_idempotent_and_byte_stable(self) -> None:
        self.build()
        first = export_ledger(self.store)
        path = Path(first["path"])
        original = path.read_bytes()

        second = export_ledger(self.store)

        self.assertFalse(first["unchanged"])
        self.assertTrue(second["unchanged"])
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(path.read_bytes(), original)

    def test_export_preserves_every_command_verbatim(self) -> None:
        self.build()
        export_ledger(self.store)
        path = self.root / LEDGER_RELATIVE

        events = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        self.assertEqual(len(events), len(self.commands()))
        for row, event in zip(self.commands(), events):
            self.assertEqual(event["command_id"], row["command_id"])
            self.assertEqual(event["action"], row["action"])
            self.assertEqual(event["request_hash"], row["request_hash"])
            self.assertEqual(event["created_at"], row["created_at"])
            self.assertEqual(event["origin_revision"], row["origin_revision"])
            self.assertEqual(event["request"], json.loads(row["request_json"]))
            self.assertEqual(event["receipt"], json.loads(row["receipt_json"]))
            self.assertEqual(
                json.dumps(event["request"], ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")),
                row["request_json"],
            )

    def test_export_refuses_non_contiguous_sequences(self) -> None:
        rows = [
            {"local_sequence": 1, "command_id": "a", "request_json": "{}",
             "receipt_json": "{}", "origin_kind": "local", "origin_context_id": "c",
             "origin_revision": 1, "action": "goal.create", "request_hash": "h",
             "created_at": "t"},
            {"local_sequence": 3, "command_id": "b", "request_json": "{}",
             "receipt_json": "{}", "origin_kind": "local", "origin_context_id": "c",
             "origin_revision": 3, "action": "goal.create", "request_hash": "h",
             "created_at": "t"},
        ]
        with self.assertRaises(StateError):
            render_ledger(rows)

    def test_verify_ledger_matches_and_reports_drift(self) -> None:
        self.build()
        export_ledger(self.store)

        report = verify_ledger(self.root, self.store)
        self.assertTrue(report["matches"])
        self.assertEqual(report["mismatches"], [])
        self.assertEqual(report["logical_state_hash"], logical_state_hash(self.live()))

        path = self.root / LEDGER_RELATIVE
        path.write_text("", encoding="utf-8")
        drifted = verify_ledger(self.root, self.store)
        self.assertFalse(drifted["matches"])
        self.assertIn("tasks", drifted["mismatches"])

    def test_ledger_path_is_project_local(self) -> None:
        self.assertEqual(
            ledger_path(self.root),
            (self.root / ".project-log" / "ledger" / "v1" / "ledger.jsonl").resolve(),
        )


if __name__ == "__main__":
    unittest.main()
