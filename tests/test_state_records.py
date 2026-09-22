"""Lifecycle records, links, evidence and reviews in transactional format 2."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = SCRIPTS / "vibe.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import StateError, Store  # noqa: E402


class RecordStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project_id = uuid.uuid4().hex
        self.context_id = "a" * 64
        self.store = Store(self.root / "state.sqlite3", self.project_id, self.context_id)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def apply(self, action: str, payload: dict) -> dict:
        return self.store.apply({
            "schema_version": 1,
            "command_id": uuid.uuid4().hex,
            "expected_revision": self.store.status()["revision"],
            "action": action,
            "payload": payload,
        })

    def assert_error(self, code: str, action: str, payload: dict) -> None:
        with self.assertRaises(StateError) as caught:
            self.apply(action, payload)
        self.assertEqual(caught.exception.code, code)

    def test_all_record_kinds_can_be_created_updated_and_linked(self) -> None:
        definitions = (
            ("business-atom", "draft", "active", {}),
            ("requirement", "draft", "active", {"approval": {"status": "pending"}}),
            ("decision", "proposed", "active", {"authority": "B"}),
            ("architecture", "draft", "active", {}),
            ("research", "draft", "complete", {}),
            ("alignment", "open", "resolved", {}),
            ("retrospective", "draft", "complete", {}),
            ("distillation", "candidate", "approved", {}),
        )
        identifiers = []
        for kind, initial, final, payload in definitions:
            record_id = f"{kind.upper().replace('-', '_')}-001"
            identifiers.append((kind, record_id))
            result = self.apply("record.create", {
                "kind": kind, "id": record_id, "title": f"Title {kind}",
                "status": initial, "payload": payload,
            })
            self.assertEqual(result["result"]["revision"], 1)
            updated = self.apply("record.update", {
                "kind": kind, "id": record_id, "expected_record_revision": 1,
                "status": final, "payload": {"updated": True},
            })
            self.assertEqual(updated["result"]["revision"], 2)
        self.apply("record.link", {
            "from_kind": identifiers[0][0], "from_id": identifiers[0][1],
            "relation": "references", "to_kind": identifiers[1][0], "to_id": identifiers[1][1],
        })

        self.assertEqual(len(self.store.list_records()), 8)
        self.assertEqual(len(self.store.list_record_links()), 1)
        self.assertEqual(self.store.get_record(*identifiers[0])["status"], "active")
        self.assertEqual(self.store.validate(), [])

    def test_unknown_kind_and_relation_fail_explicitly(self) -> None:
        self.assert_error("unsupported_record_kind", "record.create", {
            "kind": "free-text", "id": "X-001", "title": "X", "status": "draft",
        })
        self.apply("record.create", {
            "kind": "business-atom", "id": "BL-001", "title": "X",
            "status": "draft", "payload": {},
        })
        self.assert_error("invalid_input", "record.link", {
            "from_kind": "business-atom", "from_id": "BL-001",
            "relation": "invented", "to_kind": "business-atom", "to_id": "BL-001",
        })

    def test_c_level_decision_requires_explicit_user_approval(self) -> None:
        self.assert_error("invalid_input", "record.create", {
            "kind": "decision", "id": "DEC-001", "title": "C decision",
            "status": "proposed", "payload": {"authority": "C"},
        })
        self.apply("record.create", {
            "kind": "decision", "id": "DEC-002", "title": "Approved C decision",
            "status": "proposed",
            "payload": {"authority": "C", "user_approval": "approved"},
        })

    def test_long_form_body_is_rejected_from_structured_store(self) -> None:
        self.assert_error("document_body_not_allowed", "record.create", {
            "kind": "research", "id": "RES-001", "title": "Research",
            "status": "draft", "payload": {"body": "x" * 4097},
        })
        # Long-form text is rejected at any depth, including nested keys.
        self.assert_error("document_body_not_allowed", "record.create", {
            "kind": "research", "id": "RES-002", "title": "Research",
            "status": "draft", "payload": {"notes": "x" * 17000},
        })
        self.assert_error("document_body_not_allowed", "record.create", {
            "kind": "research", "id": "RES-004", "title": "Research",
            "status": "draft", "payload": {"meta": {"body": "x" * 5000}},
        })
        # Many short strings still hit the encoded payload cap.
        self.assert_error("invalid_input", "record.create", {
            "kind": "research", "id": "RES-005", "title": "Research",
            "status": "draft",
            "payload": {f"k{index}": "y" * 100 for index in range(200)},
        })
        self.apply("record.create", {
            "kind": "research", "id": "RES-003", "title": "Research",
            "status": "draft",
            "payload": {"doc_ref": {"path": ".project-log/docs/research.md", "sha256": "b" * 64}},
        })
        self.assertEqual(
            self.store.get_record("research", "RES-003")["payload"]["doc_ref"]["sha256"],
            "b" * 64,
        )

    def test_evidence_invalidation_preserves_history(self) -> None:
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "record storage",
            "status": "valid", "covers": {"files": ["runtime/scripts/state_store.py"]},
            "version_binding": {"file_hashes": {"runtime/scripts/state_store.py": "c" * 64}},
        })
        self.apply("evidence.invalidate", {"id": "EVID-001", "reason": "covered file changed"})

        evidence = self.store.get_evidence("EVID-001")
        self.assertEqual(evidence["status"], "stale")
        self.assertEqual(evidence["invalidation_reason"], "covered file changed")
        self.assertEqual(evidence["version_binding"]["file_hashes"][
            "runtime/scripts/state_store.py"
        ], "c" * 64)
        self.assertEqual(self.store.validate(), [])

    def test_review_refs_must_point_to_existing_evidence(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"})
        self.assert_error("not_found", "review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "reviewer",
            "verdict": "go", "scope": {"acceptance": ["AC-001"]},
            "evidence_refs": ["EVID-MISSING"],
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
        })
        self.apply("review.record", {
            "id": "REV-002", "task_id": "TASK-001", "reviewer": "reviewer",
            "verdict": "go", "scope": {"acceptance": ["AC-001"]},
            "evidence_refs": ["EVID-001"],
        })
        self.assertEqual(self.store.list_reviews("TASK-001")[0]["evidence_refs"], ["EVID-001"])
        self.assertEqual(self.store.validate(), [])

    def test_export_import_preserves_records_links_evidence_and_reviews(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"})
        self.apply("record.create", {
            "kind": "business-atom", "id": "BL-001", "title": "Atom",
            "status": "active", "payload": {"rule": "one"},
        })
        self.apply("record.create", {
            "kind": "decision", "id": "DEC-001", "title": "Decision",
            "status": "active", "payload": {"authority": "B"},
        })
        self.apply("record.link", {
            "from_kind": "decision", "from_id": "DEC-001",
            "relation": "implements", "to_kind": "business-atom", "to_id": "BL-001",
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "atom",
            "status": "valid", "task_id": "TASK-001",
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "reviewer",
            "verdict": "go", "scope": {"acceptance": ["AC-001"]},
            "evidence_refs": ["EVID-001"],
        })

        target = Store(self.root / "target.sqlite3", self.project_id, "b" * 64)
        target.initialize()
        result = target.apply_import(self.store.export_bundle(), "d" * 64)

        self.assertEqual(result["status"], "imported")
        self.assertEqual(target.get_record("business-atom", "BL-001")["payload"]["rule"], "one")
        self.assertEqual(target.list_record_links()[0]["relation"], "implements")
        self.assertEqual(target.get_evidence("EVID-001")["status"], "valid")
        self.assertEqual(target.list_reviews("TASK-001")[0]["verdict"], "go")
        self.assertEqual(target.validate(), [])

    def test_cli_record_and_evidence_commands_use_the_same_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            initialized = subprocess.run(
                [sys.executable, str(VIBE), "--root", str(target), "init"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stdout)
            result = subprocess.run(
                [
                    sys.executable, str(VIBE), "--root", str(target),
                    "record", "create", "--kind", "business-atom",
                    "--id", "BL-CLI-001", "--title", "CLI atom",
                    "--status", "draft", "--payload", "{}",
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("BL-CLI-001", result.stdout)


if __name__ == "__main__":
    unittest.main()
