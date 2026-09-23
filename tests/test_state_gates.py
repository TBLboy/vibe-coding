"""Evidence and review gates for transactional tasks and goals."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
import sys

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import StateError, Store  # noqa: E402
from state_context import initialize as initialize_project, open_store  # noqa: E402
from state_context import refresh_evidence  # noqa: E402


class GateStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "state.sqlite3", uuid.uuid4().hex, "c" * 64)
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

    def begin_task(self, *, risk: str = "normal") -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": risk, "implementer": "implementer-a"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })

    def test_task_finish_requires_valid_evidence_covering_the_task(self) -> None:
        self.begin_task()
        self.assert_error("task_gate", "task.finish", {
            "task_id": "TASK-001", "summary": "implemented",
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        result = self.apply("task.finish", {
            "task_id": "TASK-001", "summary": "implemented",
        })
        self.assertEqual(result["result"]["status"], "implemented-unverified")

    def test_gate_names_the_covers_binding_when_evidence_only_carries_task_id(self) -> None:
        """A task_id attribution is not a coverage claim, and the gate must say so."""
        self.begin_task()
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
        })
        blocking = " ".join(self.store.gate_task("TASK-001")["blocking"])
        self.assertIn("no valid evidence covers task TASK-001", blocking)
        self.assertIn("covers.tasks", blocking)
        self.assertIn("EVID-001", blocking)

    def test_gate_explains_how_to_cover_a_task_with_no_evidence(self) -> None:
        self.begin_task()
        blocking = " ".join(self.store.gate_task("TASK-001")["blocking"])
        self.assertIn("no valid evidence covers task TASK-001", blocking)
        self.assertIn("covers.tasks", blocking)
        self.assertNotIn("attributed to this task by task_id", blocking)

    def test_gate_does_not_claim_missing_covers_when_covering_evidence_is_stale(self) -> None:
        """Covering evidence that went stale must not be reported as uncovered."""
        project = self.root / "stale-worktree"
        project.mkdir()
        artifact = project / "artifact.txt"
        artifact.write_text("before\n", encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        store = Store(project / "state.sqlite3", uuid.uuid4().hex, "f" * 64, project)
        store.initialize()

        def apply(action: str, payload: dict) -> dict:
            return store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": action, "payload": payload,
            })

        apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal", "implementer": "implementer-a"},
        })
        apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })
        apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "artifact",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"], "files": ["artifact.txt"]},
            "version_binding": {"file_hashes": {"artifact.txt": digest}},
        })
        artifact.write_text("after\n", encoding="utf-8")
        blocking = " ".join(store.gate_task("TASK-001")["blocking"])
        self.assertIn("covering task TASK-001 is stale", blocking)
        self.assertIn("covers.tasks", blocking)
        self.assertNotIn("does not declare covers.tasks", blocking)

    def test_high_risk_task_requires_independent_go_review(self) -> None:
        self.begin_task(risk="high")
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.assert_error("task_gate", "task.finish", {
            "task_id": "TASK-001", "summary": "implemented",
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        self.assertEqual(self.store.gate_task("TASK-001")["decision"], "allowed")
        self.apply("task.finish", {"task_id": "TASK-001", "summary": "implemented"})

    def test_high_risk_review_must_be_bound_to_current_evidence(self) -> None:
        self.begin_task(risk="high")
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": [],
        })
        decision = self.store.gate_task("TASK-001")
        self.assertEqual(decision["decision"], "blocked")
        self.assertTrue(
            any("bound to current evidence" in problem for problem in decision["blocking"]),
            decision["blocking"],
        )
        self.assert_error("task_gate", "task.finish", {
            "task_id": "TASK-001", "summary": "implemented",
        })

    def test_high_risk_task_without_implementer_fails_closed(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": "high"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        decision = self.store.gate_task("TASK-001")
        self.assertEqual(decision["decision"], "blocked")
        self.assertTrue(
            any("no recorded implementer" in problem for problem in decision["blocking"]),
            decision["blocking"],
        )

    def test_stale_covered_artifact_blocks_completion_without_refresh(self) -> None:
        project = self.root / "worktree"
        project.mkdir()
        artifact = project / "artifact.txt"
        artifact.write_text("verified bytes", encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        store = Store(project / "state.sqlite3", uuid.uuid4().hex, "e" * 64, project)
        store.initialize()

        def apply(action: str, payload: dict) -> dict:
            return store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": action, "payload": payload,
            })

        apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal", "implementer": "implementer-a"},
        })
        apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })
        apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
            "version_binding": {"file_hashes": {"artifact.txt": digest}},
        })
        self.assertEqual(store.gate_task("TASK-001")["decision"], "allowed")

        artifact.write_text("changed bytes", encoding="utf-8")

        decision = store.gate_task("TASK-001")
        self.assertEqual(decision["decision"], "blocked")
        self.assertTrue(
            any("stale" in problem for problem in decision["blocking"]), decision["blocking"]
        )
        with self.assertRaises(StateError) as caught:
            apply("task.finish", {"task_id": "TASK-001", "summary": "implemented"})
        self.assertEqual(caught.exception.code, "task_gate")

    def test_goal_completion_rejects_evidence_whose_artifact_changed(self) -> None:
        project = self.root / "goal-worktree"
        project.mkdir()
        artifact = project / "artifact.txt"
        artifact.write_text("verified bytes", encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        store = Store(project / "state.sqlite3", uuid.uuid4().hex, "f" * 64, project)
        store.initialize()

        def apply(action: str, payload: dict) -> dict:
            return store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": action, "payload": payload,
            })

        apply("goal.create", {
            "id": "GOAL-001", "title": "Goal",
            "extensions": {
                "success_conditions": [{
                    "id": "SC-001", "status": "passed", "evidence_refs": ["EVID-001"],
                }],
                "required_evidence": [{"kind": "test", "subject": "goal"}],
                "risk_level": "normal",
            },
        })
        apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "goal", "status": "valid",
            "version_binding": {"file_hashes": {"artifact.txt": digest}},
        })
        self.assertTrue(store.evaluate_goal("GOAL-001")["passed"])

        artifact.write_text("changed bytes", encoding="utf-8")

        result = store.evaluate_goal("GOAL-001")
        self.assertFalse(result["passed"])
        self.assertTrue(any("stale" in reason for reason in result["reasons"]), result["reasons"])

    def test_goal_completion_requires_condition_and_required_evidence(self) -> None:
        self.apply("goal.create", {
            "id": "GOAL-001", "title": "Goal",
            "extensions": {
                "success_conditions": [{
                    "id": "SC-001", "status": "passed", "evidence_refs": ["EVID-GOAL"],
                }],
                "required_evidence": [{
                    "kind": "test", "subject": "goal", "evidence_refs": ["EVID-GOAL"],
                }],
                "risk_level": "normal",
            },
        })
        self.assert_error("goal_gate", "goal.complete", {"id": "GOAL-001"})
        self.apply("evidence.record", {
            "id": "EVID-GOAL", "kind": "test", "subject": "goal", "status": "valid",
        })
        result = self.apply("goal.complete", {"id": "GOAL-001"})
        self.assertEqual(result["result"]["status"], "complete")
        self.assertTrue(self.store.evaluate_goal("GOAL-001")["passed"])

    def test_not_applicable_condition_requires_an_explicit_reason(self) -> None:
        self.apply("goal.create", {
            "id": "GOAL-NA", "title": "Goal",
            "extensions": {
                "success_conditions": [{"id": "SC-001", "status": "not-applicable"}],
                "required_evidence": [],
                "risk_level": "normal",
            },
        })
        self.assert_error("goal_gate", "goal.complete", {"id": "GOAL-NA"})
        # Replace the goal's extension by importing a corrected record through a
        # fresh store; the command surface intentionally has no silent goal update.
        target = Store(self.root / "corrected.sqlite3", self.store.project_id, "d" * 64)
        target.initialize()
        target.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 0, "action": "goal.create",
            "payload": {
                "id": "GOAL-NA", "title": "Goal",
                "extensions": {
                    "success_conditions": [{
                        "id": "SC-001", "status": "not-applicable",
                        "reason": "no user-facing surface in this increment",
                    }],
                    "required_evidence": [],
                    "risk_level": "normal",
                },
            },
        })
        result = target.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 1, "action": "goal.complete",
            "payload": {"id": "GOAL-NA"},
        })
        self.assertEqual(result["result"]["status"], "complete")

    def test_changed_covered_file_makes_evidence_stale(self) -> None:
        covered = self.root / "artifact.txt"
        covered.write_text("before\n", encoding="utf-8")
        digest = __import__("hashlib").sha256(covered.read_bytes()).hexdigest()
        self.apply("evidence.record", {
            "id": "EVID-FILE", "kind": "test", "subject": "artifact",
            "status": "valid",
            "covers": {"files": ["artifact.txt"]},
            "version_binding": {"file_hashes": {"artifact.txt": digest}},
        })
        self.assertEqual(self.store.stale_evidence(self.root), [])
        covered.write_text("after\n", encoding="utf-8")
        stale = self.store.stale_evidence(self.root)
        self.assertEqual([item["id"] for item in stale], ["EVID-FILE"])
        self.assertIn("covered input changed: artifact.txt", stale[0]["reasons"][0])

    def test_refresh_evidence_records_invalidation_through_the_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            store = initialize_project(project)
            covered = project / "artifact.txt"
            covered.write_text("before\n", encoding="utf-8")
            digest = __import__("hashlib").sha256(covered.read_bytes()).hexdigest()
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": 0, "action": "evidence.record",
                "payload": {
                    "id": "EVID-FILE", "kind": "test", "subject": "artifact",
                    "status": "valid",
                    "covers": {"files": ["artifact.txt"]},
                    "version_binding": {"file_hashes": {"artifact.txt": digest}},
                },
            })
            covered.write_text("after\n", encoding="utf-8")
            result = refresh_evidence(project, "artifact changed after verification")
            self.assertEqual(result["invalidated"], ["EVID-FILE"])
            refreshed = open_store(project).get_evidence("EVID-FILE")
            self.assertEqual(refreshed["status"], "stale")
            self.assertEqual(refreshed["invalidation_reason"], "artifact changed after verification")

    def test_changed_doc_ref_propagates_into_task_and_goal_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            store = initialize_project(project)
            document = project / ".project-log" / "docs" / "note.md"
            document.parent.mkdir(parents=True, exist_ok=True)
            document.write_text("# Original\n", encoding="utf-8")
            digest = hashlib.sha256(document.read_bytes()).hexdigest()
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "record.create",
                "payload": {
                    "kind": "research", "id": "RES-DOC", "title": "Document",
                    "status": "complete",
                    "payload": {
                        "doc_ref": {
                            "path": ".project-log/docs/note.md",
                            "sha256": digest,
                        },
                    },
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.create",
                "payload": {"id": "GOAL-DOC", "title": "Document goal"},
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "task.create",
                "payload": {
                    "id": "TASK-DOC", "title": "Document task", "goal_id": "GOAL-DOC",
                    "extensions": {"risk": "normal", "implementer": "builder"},
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "evidence.record",
                "payload": {
                    "id": "EVID-DOC", "kind": "review", "subject": "document record",
                    "status": "valid", "task_id": "TASK-DOC",
                    "covers": {"tasks": ["TASK-DOC"]},
                },
            })
            self.assertEqual(open_store(project).gate_task("TASK-DOC")["decision"], "allowed")
            document.write_text("# Changed\n", encoding="utf-8")
            gate = open_store(project).gate_task("TASK-DOC")
            self.assertEqual(gate["decision"], "blocked")
            self.assertTrue(
                any("doc_ref changed" in problem for problem in gate["blocking"]),
                gate["blocking"],
            )
            self.assertTrue(
                any("doc_ref changed" in problem for problem in open_store(project).validate()),
            )

    def test_task_update_records_implementer_and_keeps_risk_frozen(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": "high"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "artifact",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.assertIn(
            "high-risk task TASK-001 lacks an independent review",
            " ".join(self.store.gate_task("TASK-001")["blocking"]),
        )
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "reviewer-a",
            "verdict": "go", "scope": {}, "evidence_refs": ["EVID-001"],
        })
        self.assertIn(
            "high-risk task TASK-001 has no recorded implementer",
            " ".join(self.store.gate_task("TASK-001")["blocking"]),
        )
        self.apply("task.update", {"task_id": "TASK-001", "implementer": "builder"})
        self.assertEqual(self.store.gate_task("TASK-001")["decision"], "allowed")
        # Attribution only: risk stays frozen so task.update cannot loosen a gate.
        self.assert_error("invalid_input", "task.update", {
            "task_id": "TASK-001", "implementer": "builder", "risk": "normal",
        })
        self.assert_error("invalid_input", "task.update", {"task_id": "TASK-001"})

    def test_goal_update_marks_success_conditions_and_keeps_risk_frozen(self) -> None:
        self.apply("goal.create", {
            "id": "GOAL-001", "title": "Goal",
            "extensions": {
                "risk_level": "normal",
                "success_conditions": [
                    {"id": "SC-1", "statement": "x", "status": "pending", "evidence_refs": []},
                ],
                "required_evidence": [],
            },
        })
        self.apply("evidence.record", {
            "id": "EVID-1", "kind": "test", "subject": "s", "status": "valid",
        })
        self.assert_error("goal_gate", "goal.complete", {"id": "GOAL-001"})
        self.apply("goal.update", {
            "id": "GOAL-001",
            "success_conditions": [
                {"id": "SC-1", "statement": "x", "status": "passed", "evidence_refs": ["EVID-1"]},
            ],
        })
        self.assertEqual(
            self.apply("goal.complete", {"id": "GOAL-001"})["result"]["status"], "complete"
        )
        # Only the evidence-accruing fields move; risk_level stays frozen.
        self.assert_error("invalid_input", "goal.update", {"id": "GOAL-001", "risk_level": "high"})
        self.assert_error("invalid_input", "goal.update", {"id": "GOAL-001"})

    def test_multiple_active_goals_fail_closed_instead_of_picking_the_earliest(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Earlier"})
        self.apply("goal.create", {"id": "GOAL-002", "title": "Later"})
        problems = [item for item in self.store.audit_gates() if "multiple active goals" in item]
        self.assertEqual(len(problems), 1, self.store.audit_gates())
        self.assertIn("GOAL-001", problems[0])
        self.assertIn("GOAL-002", problems[0])
        self.assertEqual(self.store.active_goal_ids(), ["GOAL-001", "GOAL-002"])
        # The default target refuses to guess: the ambiguity is a hard error rather
        # than a silent answer with the earliest goal.
        with self.assertRaises(StateError) as caught:
            self.store.active_goal_id()
        self.assertEqual(caught.exception.code, "state_conflict")

    def test_audit_stays_quiet_with_a_single_active_goal(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Only"})
        self.assertEqual(
            [item for item in self.store.audit_gates() if "multiple active goals" in item],
            [],
        )

    def test_active_goal_id_without_any_goal_reports_not_found(self) -> None:
        self.assertEqual(self.store.active_goal_ids(), [])
        with self.assertRaises(StateError) as caught:
            self.store.active_goal_id()
        self.assertEqual(caught.exception.code, "not_found")

    def _project_with_goals(self, project: Path, goal_ids: tuple[str, ...]) -> None:
        store = initialize_project(project)
        for goal_id in goal_ids:
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": "goal.create",
                "payload": {"id": goal_id, "title": goal_id},
            })

    def test_compact_context_marks_the_goal_ambiguous_instead_of_guessing(self) -> None:
        from state_context import compact_context

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._project_with_goals(project, ("GOAL-001", "GOAL-002"))
            context = compact_context(project)
            self.assertIn("Project goal: ambiguous (GOAL-001, GOAL-002)", context)

    def test_compact_context_names_the_single_active_goal(self) -> None:
        from state_context import compact_context

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._project_with_goals(project, ("GOAL-001",))
            context = compact_context(project)
            self.assertIn("Project goal: GOAL-001", context)
            self.assertNotIn("ambiguous", context)


if __name__ == "__main__":
    unittest.main()
