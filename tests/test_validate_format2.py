"""TASK-041: format 2 validation covers gates, payloads and migration state."""
from __future__ import annotations

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

from state_context import initialize, open_store  # noqa: E402
from validate_package import validate as validate_package  # noqa: E402
from validate_project import validate  # noqa: E402


class FormatTwoValidationTests(unittest.TestCase):
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

    def test_valid_format_two_project_passes(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"})
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.apply("task.finish", {"task_id": "TASK-001", "summary": "implemented"})

        self.assertEqual(validate(self.root), [])

    def test_package_validation_covers_transactional_runtime_assets(self) -> None:
        self.assertEqual(validate_package(ROOT), [])

    def test_completed_task_without_evidence_fails_gate_validation(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"})
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })
        connection = sqlite3.connect(self.store.path)
        connection.execute(
            "UPDATE tasks SET status = 'implemented-unverified', summary = 'forged' WHERE id = 'TASK-001'"
        )
        connection.execute("UPDATE runs SET status = 'finished' WHERE id = 'RUN-001'")
        connection.commit()
        connection.close()

        errors = validate(self.root)

        self.assertTrue(any("TASK-001" in error and "no valid evidence" in error for error in errors))

    def test_long_form_payload_in_storage_is_rejected(self) -> None:
        self.apply("record.create", {
            "kind": "research", "id": "RES-001", "title": "Research",
            "status": "draft", "payload": {"doc_ref": {"path": "x.md", "sha256": "a" * 64}},
        })
        connection = sqlite3.connect(self.store.path)
        connection.execute(
            "UPDATE records SET payload = ? WHERE kind = 'research' AND id = 'RES-001'",
            (json.dumps({"body": "x" * 5000}),),
        )
        connection.commit()
        connection.close()

        errors = validate(self.root)

        self.assertTrue(any("payload.body carries long-form text" in error for error in errors))

    def test_nested_long_form_payload_in_storage_is_rejected(self) -> None:
        self.apply("record.create", {
            "kind": "research", "id": "RES-002", "title": "Research",
            "status": "draft", "payload": {"doc_ref": {"path": "x.md", "sha256": "a" * 64}},
        })
        connection = sqlite3.connect(self.store.path)
        connection.execute(
            "UPDATE records SET payload = ? WHERE kind = 'research' AND id = 'RES-002'",
            (json.dumps({"meta": {"body": "x" * 5000}}),),
        )
        connection.commit()
        connection.close()

        errors = validate(self.root)

        self.assertTrue(
            any("payload.meta.body carries long-form text" in error for error in errors), errors
        )

    def test_record_doc_ref_hash_is_re_evaluated_by_validation(self) -> None:
        document = self.root / ".project-log/docs/research.md"
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text("# Research\n", encoding="utf-8")
        import hashlib

        digest = hashlib.sha256(document.read_bytes()).hexdigest()
        self.apply("record.create", {
            "kind": "research", "id": "RES-003", "title": "Research",
            "status": "draft",
            "payload": {"doc_ref": {"path": ".project-log/docs/research.md", "sha256": digest}},
        })
        self.assertEqual(validate(self.root), [])

        document.write_text("# Research v2\n", encoding="utf-8")

        errors = validate(self.root)
        self.assertTrue(any("doc_ref changed" in error for error in errors), errors)

    def test_failed_migration_journal_is_reported(self) -> None:
        migration = self.root / ".project-log/.migration"
        migration.mkdir()
        (migration / "journal.json").write_text(
            json.dumps({"status": "failed", "error": "simulated switch failure"}) + "\n",
            encoding="utf-8",
        )

        errors = validate(self.root)

        self.assertTrue(any("failed switch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
