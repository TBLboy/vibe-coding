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
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
        })

    @staticmethod
    def run_binding(owner: str, session_id: str, write_scope: list[str]) -> dict:
        return {"owner": owner, "session_id": session_id, "write_scope": write_scope}

    def test_disjoint_scoped_runs_can_be_active_together(self) -> None:
        """The former global active slot must not serialize independent work."""
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        for task_id in ("TASK-A", "TASK-B"):
            self.apply("task.create", {
                "id": task_id, "title": task_id, "goal_id": "GOAL-001",
                "extensions": {"risk": "normal", "implementer": task_id},
            })
        self.apply("task.begin", {
            "task_id": "TASK-A", "run_id": "RUN-A", "next_action": "write a",
            **self.run_binding("agent-a", "session-a", ["module_a"]),
        })
        self.apply("task.begin", {
            "task_id": "TASK-B", "run_id": "RUN-B", "next_action": "write b",
            **self.run_binding("agent-b", "session-b", ["module_b/subdir"]),
        })
        state = self.store.status()
        self.assertEqual([row["id"] for row in state["active_runs"]], ["RUN-A", "RUN-B"])
        self.assertEqual({row["id"] for row in state["active_tasks"]}, {"TASK-A", "TASK-B"})
        self.assertIsNone(state["current_run"], "a scalar current Run is ambiguous under concurrency")
        self.store._audit()

    def test_overlapping_scoped_runs_are_rejected_without_changing_first_run(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        for task_id in ("TASK-A", "TASK-B"):
            self.apply("task.create", {"id": task_id, "title": task_id, "goal_id": "GOAL-001"})
        self.apply("task.begin", {
            "task_id": "TASK-A", "run_id": "RUN-A", "next_action": "write a",
            **self.run_binding("agent-a", "session-a", ["module"]),
        })
        self.assert_error("scope_conflict", "task.begin", {
            "task_id": "TASK-B", "run_id": "RUN-B", "next_action": "write b",
            **self.run_binding("agent-b", "session-b", ["module/child"]),
        })
        self.assertEqual(self.store.get_task("TASK-B")["status"], "ready")
        self.assertEqual([row["id"] for row in self.store.status()["active_runs"]], ["RUN-A"])

    def test_run_binding_is_required_and_scope_is_literal_project_relative(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"})
        self.assert_error("invalid_input", "task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "work",
        })
        self.assert_error("invalid_input", "task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "work",
            **self.run_binding("agent", "session", ["../outside"]),
        })

    def test_generated_views_render_every_active_scoped_run(self) -> None:
        """Concurrent state must not crash or hide an active Run in generated handoff."""
        from state_views import publish

        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        for task_id, run_id, scope in (("TASK-A", "RUN-A", "module_a"), ("TASK-B", "RUN-B", "module_b")):
            self.apply("task.create", {"id": task_id, "title": task_id, "goal_id": "GOAL-001"})
            self.apply("task.begin", {
                "task_id": task_id, "run_id": run_id, "next_action": "work",
                **self.run_binding(task_id, "session-" + task_id, [scope]),
            })
        result = publish(self.store, self.root / "generated")
        generation = Path(result["destination"]) / result["generation"]
        for name in ("current-session.md", "handoff.md"):
            content = (generation / name).read_text(encoding="utf-8")
            self.assertIn("RUN-A", content)
            self.assertIn("RUN-B", content)
            self.assertIn("owner: TASK-A", content)
            self.assertIn("session: session-TASK-A", content)
            # Views escape Markdown metacharacters, so the scope is visible but `_`
            # is rendered as `\_` rather than being interpreted as emphasis.
            self.assertIn("module\\_a", content)
            self.assertIn("module\\_b", content)

    def test_resume_rechecks_scope_against_a_new_active_run(self) -> None:
        """A paused Run cannot regain an overlapping scope after another Run starts."""
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        for task_id in ("TASK-A", "TASK-B"):
            self.apply("task.create", {"id": task_id, "title": task_id, "goal_id": "GOAL-001"})
        self.apply("task.begin", {
            "task_id": "TASK-A", "run_id": "RUN-A", "next_action": "work",
            **self.run_binding("agent-a", "session-a", ["module"]),
        })
        self.apply("task.handoff", {"task_id": "TASK-A", "next_action": "resume later"})
        self.apply("task.begin", {
            "task_id": "TASK-B", "run_id": "RUN-B", "next_action": "work",
            **self.run_binding("agent-b", "session-b", ["module/child"]),
        })
        self.assert_error("scope_conflict", "task.resume", {
            "task_id": "TASK-A", "next_action": "resume now",
        })
        self.assertEqual(self.store.get_task("TASK-A")["status"], "handed-off")
        self.assertEqual(self.store.get_task("TASK-B")["status"], "in-progress")

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
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
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
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
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

    def test_strict_task_with_only_unverifiable_mechanical_evidence_is_not_confirmed(self) -> None:
        """T22: a record that claims a version binding must be re-evaluable.

        `version_binding` is the record saying "this result belongs to specific bytes".
        When it carries a commit but no file hashes, nobody — not the gate, not a later
        reviewer — can re-derive that claim. A strict task covered only by such records
        must fail closed instead of reading as mechanically verified.
        """
        self.begin_task(risk="strict")
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
            "version_binding": {"git_commit": "abc123"},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        decision = self.store.gate_task("TASK-001")
        self.assertEqual(decision["decision"], "blocked")
        self.assertTrue(
            any("mechanical verification is not confirmed" in problem
                for problem in decision["blocking"]),
            decision["blocking"],
        )
        self.assert_error("task_gate", "task.finish", {
            "task_id": "TASK-001", "summary": "implemented",
        })

    def test_both_strictness_vocabularies_are_treated_as_strict(self) -> None:
        """`risk: strict` is the routing word for tasks; `high`/`critical` are the goals'.

        The T22 floor has to fire for both, or a strict task could pick the vocabulary
        that happens not to be checked.
        """
        for risk in ("strict", "high", "critical"):
            with self.subTest(risk=risk):
                self.setUp()
                try:
                    self.begin_task(risk=risk)
                    self.apply("evidence.record", {
                        "id": "EVID-001", "kind": "test", "subject": "task",
                        "status": "valid", "task_id": "TASK-001",
                        "covers": {"tasks": ["TASK-001"]},
                        "version_binding": {"git_commit": "abc123"},
                    })
                    self.apply("review.record", {
                        "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
                        "verdict": "go", "scope": {"tasks": ["TASK-001"]},
                        "evidence_refs": ["EVID-001"],
                    })
                    blocking = " ".join(self.store.gate_task("TASK-001")["blocking"])
                    self.assertIn("mechanical verification is not confirmed", blocking, risk)
                finally:
                    self.tearDown()

    def test_bindingless_strict_evidence_is_reported_but_not_blocked(self) -> None:
        """T22/N04: unclaimed evidence must not *silently* read as mechanically reproduced.

        A manual or external check legitimately cannot carry a worktree hash, so the gate
        does not block on it — but it says out loud that re-derivation is impossible, so
        `unknown` applicability is never quietly treated as independently reproduced.
        """
        self.begin_task(risk="strict")
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "manual", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        decision = self.store.gate_task("TASK-001")
        self.assertEqual(decision["decision"], "allowed")
        self.assertTrue(
            any("mechanical reproduction is not confirmed" in note
                for note in decision["notes"]),
            decision["notes"],
        )

    def test_gate_notes_are_scoped_to_strict_tasks(self) -> None:
        """An ordinary task is never told its evidence is unverifiable: the floor is strict-only."""
        self.begin_task()
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "manual", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.assertEqual(self.store.gate_task("TASK-001")["notes"], [])

    def test_a_claimed_binding_without_hashes_blocks_instead_of_being_noted(self) -> None:
        """The claimed-binding case is a failure, not a note: it must not be double-reported."""
        self.begin_task(risk="strict")
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
            "version_binding": {"git_commit": "abc123"},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        decision = self.store.gate_task("TASK-001")
        self.assertEqual(decision["decision"], "blocked")
        self.assertTrue(
            any("mechanical verification is not confirmed" in problem
                for problem in decision["blocking"]),
            decision["blocking"],
        )
        self.assertEqual(decision["notes"], [])

    def test_strict_task_with_hash_bound_evidence_still_completes(self) -> None:
        """T22 is a floor, not a wall: a re-evaluable binding is still accepted."""
        self.begin_task(risk="high")
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
            "version_binding": {"file_hashes": {"artifact.txt": "a" * 64}},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "independent",
            "verdict": "go", "scope": {"tasks": ["TASK-001"]},
            "evidence_refs": ["EVID-001"],
        })
        self.assertEqual(self.store.gate_task("TASK-001")["decision"], "allowed")

    def test_evidence_that_claims_no_binding_is_left_alone(self) -> None:
        """The T22 floor targets claimed bindings only, so ordinary records still pass.

        Evidence with no `version_binding` at all is not asserting that it is bound to
        bytes, and the strict-task contract for it is unchanged.
        """
        self.begin_task(risk="high")
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
        self.assertEqual(self.store.gate_task("TASK-001")["decision"], "allowed")

    def test_the_unverifiable_binding_floor_is_scoped_to_strict_tasks(self) -> None:
        """An ordinary task keeps its previous contract: no new retroactive blocking."""
        self.begin_task()
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "task",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
            "version_binding": {"git_commit": "abc123"},
        })
        self.assertEqual(self.store.gate_task("TASK-001")["decision"], "allowed")

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
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
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

    def test_unresolvable_hash_keys_are_refused_at_write_time(self) -> None:
        """TASK-120: a key that names nothing is refused, not silently unverifiable.

        The store resolves relative keys against the project root, so a key written
        relative to the repository inside a nested project was accepted and then read
        forever as "the covered artifact changed" -- indistinguishable from real
        staleness, even though the recorded digest was correct.
        """
        project = self.root / "hash-keys"
        project.mkdir()
        (project / "real.txt").write_text("bytes", encoding="utf-8")
        store = Store(project / "state.sqlite3", uuid.uuid4().hex, "f" * 64, project)
        store.initialize()

        def apply(action: str, payload: dict) -> dict:
            return store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": action, "payload": payload,
            })

        with self.assertRaises(StateError) as caught:
            apply("evidence.record", {
                "id": "EVID-001", "kind": "test", "subject": "unresolvable",
                "status": "valid",
                "version_binding": {"file_hashes": {"nested/real.txt": "0" * 64}},
            })
        self.assertEqual(caught.exception.code, "invalid_input")
        self.assertIn("relative to the project root", str(caught.exception))
        self.assertIn("nested/real.txt", str(caught.exception))

        # A key relative to the project root, and an absolute one, both still work.
        for evidence_id, key in (
            ("EVID-002", "real.txt"),
            ("EVID-003", str(project / "real.txt")),
        ):
            apply("evidence.record", {
                "id": evidence_id, "kind": "test", "subject": "resolvable",
                "status": "valid",
                "version_binding": {"file_hashes": {key: "0" * 64}},
            })
            self.assertEqual(store.get_evidence(evidence_id)["status"], "valid")

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

    def test_completing_a_goal_closes_its_never_started_tasks(self) -> None:
        """A completed goal must not leave tasks that can never be started.

        `task.begin` refuses once the goal is not active, so a `ready` task under a
        completed goal could never reach a terminal state and would linger in the active
        view forever. Completion closes those rows with a reason that says why, while a
        task that really was implemented keeps its history.
        """
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
        self.apply("evidence.record", {
            "id": "EVID-GOAL", "kind": "test", "subject": "goal", "status": "valid",
        })
        self.apply("task.create", {
            "id": "TASK-001", "title": "never started", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal", "implementer": "implementer-a"},
        })
        self.apply("task.create", {
            "id": "TASK-002", "title": "really implemented", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal", "implementer": "implementer-a"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-002", "run_id": "RUN-001", "next_action": "verify",
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
        })
        self.apply("evidence.record", {
            "id": "EVID-002", "kind": "test", "subject": "task",
            "status": "valid", "covers": {"tasks": ["TASK-002"]},
        })
        self.apply("task.finish", {"task_id": "TASK-002", "summary": "done"})

        result = self.apply("goal.complete", {"id": "GOAL-001"})["result"]
        self.assertEqual(result["status"], "complete")
        # The receipt keeps its original shape on purpose: the reducer recomputes a receipt
        # and compares it with the stored one, so widening this would make every *existing*
        # `goal.complete` event fail to reduce and the live ledger unwritable.
        self.assertEqual(set(result), {"goal_id", "status"})

        closed = self.store.get_task("TASK-001")
        self.assertEqual(closed["status"], "cancelled")
        self.assertIn("goal completed", closed["cancel_reason"])
        # History is not rewritten: an implementation that really happened stays recorded.
        self.assertEqual(self.store.get_task("TASK-002")["status"], "implemented-unverified")

    def test_completing_a_goal_cancels_the_run_of_an_open_task(self) -> None:
        """An in-progress task's run must not survive its goal's completion.

        The audit invariant requires an active run to belong to a task that is really
        running. Closing the task without closing its run would leave a run pointing at a
        cancelled task, so completion cancels the run too.
        """
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
        self.apply("evidence.record", {
            "id": "EVID-GOAL", "kind": "test", "subject": "goal", "status": "valid",
        })
        self.apply("task.create", {
            "id": "TASK-001", "title": "still running", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal", "implementer": "implementer-a"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
        })
        self.assertIsNotNone(self.store.status()["current_run"])

        self.apply("goal.complete", {"id": "GOAL-001"})

        self.assertEqual(self.store.get_task("TASK-001")["status"], "cancelled")
        self.assertIsNone(self.store.status()["current_run"],
                          "the run of a cancelled task must not stay active")

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

    def test_legacy_doc_ref_drift_is_reported_but_does_not_block(self) -> None:
        """T18: an untyped legacy ``doc_ref`` declares no subject and no binding.

        V3 PR-03 stops treating it as a controlled dependency: nothing proves the record
        is load-bearing for this task, so the gate must not fail closed on it. The drift
        is still surfaced by ``validate`` as an unclassified reference, so it is never
        silently ignored either. Before PR-03 the global scan blocked every task and
        goal in the project as soon as any referenced document changed.
        """
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
                "payload": {
                    "id": "GOAL-DOC", "title": "Document goal",
                    "extensions": {
                        "risk_level": "normal",
                        "success_conditions": [{
                            "id": "SC-1", "status": "not-applicable",
                            "reason": "nothing to prove in this increment",
                        }],
                        "required_evidence": [],
                    },
                },
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
            self.assertTrue(open_store(project).evaluate_goal("GOAL-DOC")["passed"])

            document.write_text("# Changed\n", encoding="utf-8")

            gate = open_store(project).gate_task("TASK-DOC")
            self.assertEqual(gate["decision"], "allowed", gate["blocking"])
            self.assertEqual(gate["blocking"], [])
            self.assertTrue(open_store(project).evaluate_goal("GOAL-DOC")["passed"])
            diagnostics = open_store(project).validate()
            self.assertTrue(
                any("unclassified" in problem for problem in diagnostics), diagnostics
            )

    def test_task_update_records_implementer_and_keeps_risk_frozen(self) -> None:
        self.apply("goal.create", {"id": "GOAL-001", "title": "Goal"})
        self.apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": "high"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "verify",
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
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

    def test_goal_update_records_implementer_and_unblocks_the_high_risk_gate(self) -> None:
        self.apply("goal.create", {
            "id": "GOAL-001", "title": "Goal",
            "extensions": {
                "risk_level": "high",
                "success_conditions": [
                    {"id": "SC-1", "statement": "x", "status": "pending", "evidence_refs": []},
                ],
                "required_evidence": [],
            },
        })
        self.apply("task.create", {
            "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
            "extensions": {"risk": "high"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-001", "run_id": "RUN-001", "next_action": "review",
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
        })
        self.apply("evidence.record", {
            "id": "EVID-001", "kind": "test", "subject": "artifact",
            "status": "valid", "task_id": "TASK-001",
            "covers": {"tasks": ["TASK-001"]},
        })
        self.apply("review.record", {
            "id": "REV-001", "task_id": "TASK-001", "reviewer": "reviewer-a",
            "verdict": "go", "scope": {}, "evidence_refs": ["EVID-001"],
        })
        # DEC-070: the high-risk completion gate has to fail closed without goal-level
        # attribution, and `goal.update` used to be unable to supply it, so such a goal
        # could never be completed.
        self.assertIn(
            "missing_implementer", " ".join(self.store.evaluate_goal("GOAL-001")["reasons"])
        )
        self.apply("goal.update", {"id": "GOAL-001", "implementer": "implementation-builder"})
        self.assertNotIn(
            "missing_implementer", " ".join(self.store.evaluate_goal("GOAL-001")["reasons"])
        )
        # Attribution only: risk stays frozen so goal.update cannot loosen a gate, and a
        # blank attribution is refused instead of stored as an unusable value.
        self.assert_error("invalid_input", "goal.update", {"id": "GOAL-001", "risk_level": "normal"})
        self.assert_error("invalid_input", "goal.update", {"id": "GOAL-001", "implementer": "   "})
        self.assert_error("invalid_input", "goal.update", {"id": "GOAL-001", "owner": None})

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

    # --- V3 PR-00: failing counter-examples for the confirmed goal-gate defects ---
    #
    # Each test below encodes the *target* behaviour of a defect confirmed in
    # Vibe-Workflow-V3-工程改造实施方案.md (N01, D05). They are marked
    # ``expectedFailure`` on purpose: the test really does fail today, the suite stays
    # readable, and the moment the fix lands the test passes "unexpectedly", which
    # forces the decorator to be removed instead of the test being forgotten.

    def _high_risk_goal(self, goal_id: str, **extensions: object) -> None:
        """A high-risk goal whose only pending requirement is the review gate."""
        base = {
            "risk_level": "high",
            "success_conditions": [{
                "id": "SC-1",
                "status": "not-applicable",
                "reason": "no user-facing surface in this increment",
            }],
            "required_evidence": [],
        }
        base.update(extensions)
        self.apply("goal.create", {"id": goal_id, "title": goal_id, "extensions": base})

    def _task_with_review_evidence(self, task_id: str, goal_id: str, reviewer: str) -> None:
        """A normal task carrying a valid review-kind evidence row plus a go review."""
        self.apply("task.create", {
            "id": task_id, "title": task_id, "goal_id": goal_id,
            "extensions": {"risk": "normal", "implementer": "builder-" + task_id.lower()},
        })
        self.apply("evidence.record", {
            "id": "EVID-" + task_id, "kind": "review", "subject": task_id + " review",
            "status": "valid", "task_id": task_id,
            "covers": {"tasks": [task_id]},
        })
        self.apply("review.record", {
            "id": "REV-" + task_id, "task_id": task_id, "reviewer": reviewer,
            "verdict": "go", "scope": {"tasks": [task_id]},
            "evidence_refs": ["EVID-" + task_id],
        })

    def test_high_risk_goal_rejects_foreign_task_review(self) -> None:
        """N01 / T01: another goal's task review must not complete this goal.

        Fixed in V3 PR-01: reviews are scoped to the goal under evaluation (directly
        or through one of its own tasks), so GOAL-B's review cannot complete GOAL-A.
        Before the fix the gate iterated every row of ``reviews`` with no target filter.
        """
        self._high_risk_goal("GOAL-A", implementer="builder-a")
        self.apply("goal.create", {"id": "GOAL-B", "title": "Goal B"})
        self._task_with_review_evidence("TASK-B", "GOAL-B", reviewer="reviewer-b")

        result = self.store.evaluate_goal("GOAL-A")
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any("review_scope_mismatch" in reason for reason in result["reasons"]),
            result["reasons"],
        )

    def test_high_risk_goal_without_implementer_fails_closed(self) -> None:
        """N01 / T02: a high-risk goal with no implementer must fail closed.

        Fixed in V3 PR-01: the independence check no longer sits inside ``if
        implementer:`` with no else branch, so an unregistered implementer cannot
        silently satisfy the high-risk review requirement.
        """
        self._high_risk_goal("GOAL-A")
        self._task_with_review_evidence("TASK-A", "GOAL-A", reviewer="reviewer-a")

        result = self.store.evaluate_goal("GOAL-A")
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any("missing_implementer" in reason for reason in result["reasons"]),
            result["reasons"],
        )

    def test_high_risk_goal_accepts_its_own_task_review(self) -> None:
        """N01 positive control: the fix must not reject every high-risk goal.

        GOAL-A owns TASK-A; TASK-A carries a go review from someone other than the
        goal's implementer, bound to valid evidence covering TASK-A. That is exactly
        the aggregation the gate is meant to allow, so GOAL-A must still complete.
        """
        self._high_risk_goal("GOAL-A", implementer="builder-a")
        self._task_with_review_evidence("TASK-A", "GOAL-A", reviewer="reviewer-a")

        result = self.store.evaluate_goal("GOAL-A")
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["reasons"], [])

    def test_high_risk_goal_rejects_a_review_from_its_own_implementer(self) -> None:
        """N01 / T03: the reviewer must not be the goal's implementer.

        PR-01 implements the comparison (``reviewer != implementer``) but nothing
        asserted it, so the branch could regress unnoticed. The review here is otherwise
        perfect - scoped to the goal's own task, verdict ``go``, bound to valid evidence -
        so only the identity check can reject it.
        """
        self._high_risk_goal("GOAL-A", implementer="builder-a")
        self._task_with_review_evidence("TASK-A", "GOAL-A", reviewer="builder-a")

        result = self.store.evaluate_goal("GOAL-A")
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any("review_not_independent" in reason for reason in result["reasons"]),
            result["reasons"],
        )

    def test_high_risk_goal_rejects_a_review_whose_evidence_is_gone(self) -> None:
        """N01 / T04: a go review bound to unusable evidence must not pass.

        The review is independent (T03) and scoped to the goal's own task (T01), so only
        its ``evidence_refs`` are the problem. The gate must reject it for that reason
        instead of falling back to "some review exists"; an invalidated reference and a
        stale one take the same path through ``evidence_status``.
        """
        self._high_risk_goal("GOAL-A", implementer="builder-a")
        self._task_with_review_evidence("TASK-A", "GOAL-A", reviewer="reviewer-a")
        self.apply("evidence.invalidate", {"id": "EVID-TASK-A", "reason": "superseded"})

        result = self.store.evaluate_goal("GOAL-A")
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any("review_evidence_stale" in reason for reason in result["reasons"]),
            result["reasons"],
        )

    def test_unrelated_doc_ref_drift_does_not_block_an_unrelated_task(self) -> None:
        """D05 / T18: drift is scoped to the goal/task that depends on the document.

        Fixed in V3 PR-03: ``_document_drift_problems`` is scope-aware, and an untyped
        legacy ``doc_ref`` counts as informational because nothing declares it as a
        required dependency of TASK-X. The drift still reaches ``validate`` as an
        unclassified reference, so it is neither a silent pass nor a global block.
        """
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
                    "kind": "research", "id": "RES-DOC", "title": "Unrelated research",
                    "status": "complete",
                    "payload": {
                        "doc_ref": {"path": ".project-log/docs/note.md", "sha256": digest},
                    },
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.create",
                "payload": {"id": "GOAL-X", "title": "Unrelated goal"},
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "task.create",
                "payload": {
                    "id": "TASK-X", "title": "Unrelated task", "goal_id": "GOAL-X",
                    "extensions": {"risk": "normal", "implementer": "builder"},
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "evidence.record",
                "payload": {
                    "id": "EVID-X", "kind": "test", "subject": "unrelated task",
                    "status": "valid", "task_id": "TASK-X",
                    "covers": {"tasks": ["TASK-X"]},
                },
            })
            self.assertEqual(open_store(project).gate_task("TASK-X")["decision"], "allowed")

            document.write_text("# Changed\n", encoding="utf-8")

            gate = open_store(project).gate_task("TASK-X")
            self.assertEqual(gate["decision"], "allowed", gate["blocking"])
            self.assertEqual(gate["blocking"], [])
            diagnostics = open_store(project).validate()
            self.assertTrue(
                any("unclassified" in problem for problem in diagnostics), diagnostics
            )

    def test_bound_document_drift_blocks_only_its_subject(self) -> None:
        """T19: a reference that names its subject is a controlled dependency.

        The record declares ``binding: required`` for TASK-DOC, so editing the document
        must fail closed for TASK-DOC while TASK-OTHER, which depends on nothing, stays
        allowed. This is what the global scan could not express.
        """
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            store = initialize_project(project)
            document = project / ".project-log" / "docs" / "spec.md"
            document.parent.mkdir(parents=True, exist_ok=True)
            document.write_text("# Spec\n", encoding="utf-8")
            digest = hashlib.sha256(document.read_bytes()).hexdigest()
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "record.create",
                "payload": {
                    "kind": "requirement", "id": "REQ-DOC", "title": "Bound spec",
                    "status": "active",
                    "payload": {
                        "approval": {"status": "approved"},
                        "doc_ref": {
                            "type": "bound_document",
                            "path": ".project-log/docs/spec.md",
                            "sha256": digest,
                            "subject": {"kind": "task", "id": "TASK-DOC"},
                            "binding": "required",
                        },
                    },
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.create",
                "payload": {"id": "GOAL-DOC", "title": "Bound goal"},
            })
            for task_id in ("TASK-DOC", "TASK-OTHER"):
                store.apply({
                    "schema_version": 1, "command_id": uuid.uuid4().hex,
                    "expected_revision": store.status()["revision"], "action": "task.create",
                    "payload": {
                        "id": task_id, "title": task_id, "goal_id": "GOAL-DOC",
                        "extensions": {"risk": "normal", "implementer": "builder"},
                    },
                })
                store.apply({
                    "schema_version": 1, "command_id": uuid.uuid4().hex,
                    "expected_revision": store.status()["revision"], "action": "evidence.record",
                    "payload": {
                        "id": "EVID-" + task_id, "kind": "test", "subject": task_id,
                        "status": "valid", "task_id": task_id,
                        "covers": {"tasks": [task_id]},
                    },
                })
            self.assertEqual(open_store(project).gate_task("TASK-DOC")["decision"], "allowed")

            document.write_text("# Spec changed\n", encoding="utf-8")

            blocked = open_store(project).gate_task("TASK-DOC")
            self.assertEqual(blocked["decision"], "blocked", blocked)
            self.assertTrue(
                any("spec.md" in problem for problem in blocked["blocking"]),
                blocked["blocking"],
            )
            untouched = open_store(project).gate_task("TASK-OTHER")
            self.assertEqual(untouched["decision"], "allowed", untouched["blocking"])

    def test_informational_ref_drift_does_not_block(self) -> None:
        """T20: an explicitly informational reference is a diagnostic, not a gate.

        Declaring the type is what distinguishes "we point at this document" from "this
        task is only done while the document still matches".
        """
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            store = initialize_project(project)
            document = project / ".project-log" / "docs" / "background.md"
            document.parent.mkdir(parents=True, exist_ok=True)
            document.write_text("# Background\n", encoding="utf-8")
            digest = hashlib.sha256(document.read_bytes()).hexdigest()
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "record.create",
                "payload": {
                    "kind": "research", "id": "RES-INFO", "title": "Background reading",
                    "status": "complete",
                    "payload": {
                        "doc_ref": {
                            "type": "informational_ref",
                            "path": ".project-log/docs/background.md",
                            "sha256": digest,
                            "description": "context only",
                        },
                    },
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.create",
                "payload": {"id": "GOAL-INFO", "title": "Goal"},
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "task.create",
                "payload": {
                    "id": "TASK-INFO", "title": "Task", "goal_id": "GOAL-INFO",
                    "extensions": {"risk": "normal", "implementer": "builder"},
                },
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "evidence.record",
                "payload": {
                    "id": "EVID-INFO", "kind": "test", "subject": "task",
                    "status": "valid", "task_id": "TASK-INFO",
                    "covers": {"tasks": ["TASK-INFO"]},
                },
            })
            document.write_text("# Background changed\n", encoding="utf-8")

            gate = open_store(project).gate_task("TASK-INFO")
            self.assertEqual(gate["decision"], "allowed", gate["blocking"])
            diagnostics = open_store(project).validate()
            self.assertTrue(
                any("informational" in problem for problem in diagnostics), diagnostics
            )


if __name__ == "__main__":
    unittest.main()
