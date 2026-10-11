"""V3 PR-05: reopening work starts a new attempt instead of rewriting the old one.

The framework keeps one Run per Task (`runs.task_id` is unique) and `task.resume` only
accepts a paused task, so a finished or cancelled task cannot simply be pushed back to
`in-progress` without overwriting its execution history. The low-risk transition is the
one tested here: a reopen creates a *new* task that records the relation, while the old
task and its run stay exactly as they were.

The other half of PR-05 is the status projection: execution, verification and the review
verdict are separate dimensions, so "finished" no longer implies "verified".
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import StateError  # noqa: E402
from state_context import initialize, open_store  # noqa: E402


class ReopenTests(unittest.TestCase):
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

    def build_finished_task(self) -> None:
        self.apply("goal.create", {
            "id": "GOAL-1", "title": "Goal",
            "extensions": {"risk_level": "normal"},
        })
        self.apply("task.create", {
            "id": "TASK-1", "title": "First attempt", "goal_id": "GOAL-1",
            "extensions": {"risk": "normal", "implementer": "builder"},
        })
        self.apply("task.begin", {
            "task_id": "TASK-1", "run_id": "RUN-1", "next_action": "implement",
        })
        self.apply("evidence.record", {
            "id": "EVID-1", "kind": "test", "subject": "first attempt",
            "status": "valid", "task_id": "TASK-1",
            "covers": {"tasks": ["TASK-1"]},
        })
        self.apply("review.record", {
            "id": "REV-1", "task_id": "TASK-1", "reviewer": "reviewer",
            "verdict": "conditional", "scope": {"tasks": ["TASK-1"]},
            "evidence_refs": ["EVID-1"],
        })
        self.apply("task.finish", {"task_id": "TASK-1", "summary": "first attempt landed"})

    def test_reopen_creates_a_new_attempt_and_leaves_the_old_one_intact(self) -> None:
        self.build_finished_task()
        before = self.store.get_task("TASK-1")

        self.apply("task.reopen", {
            "task_id": "TASK-1", "new_task_id": "TASK-2",
            "reason": "review was conditional on the second case",
        })

        after = self.store.get_task("TASK-1")
        for field in ("status", "summary", "run_id", "extensions", "goal_id", "title"):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after["run"]["status"], "finished")
        self.assertEqual(after["review_verdict"], "conditional")

        reopened = self.store.get_task("TASK-2")
        self.assertEqual(reopened["status"], "ready")
        self.assertIsNone(reopened["run_id"])
        self.assertEqual(reopened["goal_id"], "GOAL-1")
        self.assertEqual(reopened["extensions"]["reopens"], "TASK-1")
        self.assertIn("conditional", reopened["extensions"]["reopen_reason"])
        self.assertEqual(reopened["review_verdict"], "missing")
        self.assertEqual(reopened["verification_state"], "pending")

    def test_the_new_attempt_runs_independently(self) -> None:
        self.build_finished_task()
        self.apply("task.reopen", {
            "task_id": "TASK-1", "new_task_id": "TASK-2", "reason": "second attempt",
        })
        self.apply("task.begin", {
            "task_id": "TASK-2", "run_id": "RUN-2", "next_action": "reimplement",
        })
        self.assertEqual(self.store.get_task("TASK-2")["status"], "in-progress")
        # The old run is not resurrected: one Run per Task, and history is not rewritten.
        self.assertEqual(self.store.get_task("TASK-1")["run"]["id"], "RUN-1")
        self.assertEqual(self.store.get_task("TASK-1")["run"]["status"], "finished")
        self.assertEqual(open_store(self.root).validate(), [])

    def test_reopen_accepts_a_cancelled_task(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Dropped", "goal_id": "GOAL-1"})
        self.apply("task.cancel", {"task_id": "TASK-1", "reason": "scope dropped"})
        self.apply("task.reopen", {
            "task_id": "TASK-1", "new_task_id": "TASK-2", "reason": "scope restored",
        })
        self.assertEqual(self.store.get_task("TASK-2")["status"], "ready")
        self.assertEqual(self.store.get_task("TASK-1")["status"], "cancelled")

    def test_reopen_refuses_a_task_that_is_still_open(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Open", "goal_id": "GOAL-1"})
        with self.assertRaises(StateError) as caught:
            self.apply("task.reopen", {
                "task_id": "TASK-1", "new_task_id": "TASK-2", "reason": "too early",
            })
        self.assertEqual(caught.exception.code, "state_conflict")
        self.assertIn("still ready", str(caught.exception))

    def test_reopen_refuses_an_existing_new_task_id(self) -> None:
        self.build_finished_task()
        self.apply("task.create", {"id": "TASK-2", "title": "Taken", "goal_id": "GOAL-1"})
        with self.assertRaises(StateError) as caught:
            self.apply("task.reopen", {
                "task_id": "TASK-1", "new_task_id": "TASK-2", "reason": "collision",
            })
        self.assertEqual(caught.exception.code, "state_conflict")

    def test_reopen_refuses_an_unknown_task(self) -> None:
        with self.assertRaises(StateError) as caught:
            self.apply("task.reopen", {
                "task_id": "TASK-NONE", "new_task_id": "TASK-2", "reason": "nope",
            })
        self.assertEqual(caught.exception.code, "not_found")


class DerivedStateTests(unittest.TestCase):
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

    def test_finished_does_not_imply_verified(self) -> None:
        """`implemented-unverified` stays as it is, but it must read honestly."""
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Work", "goal_id": "GOAL-1"})
        self.apply("task.begin", {
            "task_id": "TASK-1", "run_id": "RUN-1", "next_action": "implement",
        })
        self.apply("task.handoff", {"task_id": "TASK-1", "next_action": "verify"})

        task = self.store.get_task("TASK-1")
        self.assertEqual(task["status"], "handed-off")
        self.assertEqual(task["execution_state"], "paused")
        self.assertEqual(task["verification_state"], "pending")
        self.assertEqual(task["review_verdict"], "missing")

    def test_verification_and_review_are_reported_separately(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Work", "goal_id": "GOAL-1"})
        self.apply("task.begin", {
            "task_id": "TASK-1", "run_id": "RUN-1", "next_action": "implement",
        })
        self.apply("evidence.record", {
            "id": "EVID-1", "kind": "test", "subject": "work",
            "status": "valid", "task_id": "TASK-1", "covers": {"tasks": ["TASK-1"]},
        })
        self.apply("review.record", {
            "id": "REV-1", "task_id": "TASK-1", "reviewer": "reviewer",
            "verdict": "no-go", "scope": {"tasks": ["TASK-1"]},
            "evidence_refs": ["EVID-1"],
        })
        self.apply("task.finish", {"task_id": "TASK-1", "summary": "done"})

        task = self.store.get_task("TASK-1")
        # A no-go review does not complete the task: it lands as implemented-unverified.
        # That is exactly why the three dimensions are reported separately — the work is
        # executed and the evidence passed, but the verdict is not a go.
        self.assertEqual(task["status"], "implemented-unverified")
        self.assertEqual(task["execution_state"], "finished")
        self.assertEqual(task["verification_state"], "passed")
        self.assertEqual(task["review_verdict"], "no-go")

    def test_failed_evidence_reads_as_failed_not_passed(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Work", "goal_id": "GOAL-1"})
        self.apply("evidence.record", {
            "id": "EVID-1", "kind": "test", "subject": "work",
            "status": "failed", "task_id": "TASK-1", "covers": {"tasks": ["TASK-1"]},
        })
        task = self.store.get_task("TASK-1")
        self.assertEqual(task["execution_state"], "not-started")
        self.assertEqual(task["verification_state"], "failed")

    def test_a_cancelled_task_needs_no_verification(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Dropped", "goal_id": "GOAL-1"})
        self.apply("task.cancel", {"task_id": "TASK-1", "reason": "scope dropped"})
        task = self.store.get_task("TASK-1")
        self.assertEqual(task["execution_state"], "cancelled")
        self.assertEqual(task["verification_state"], "not-applicable")

    def test_the_snapshot_carries_the_derived_states(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Work", "goal_id": "GOAL-1"})
        listed = self.store.status()["tasks"]
        self.assertEqual(len(listed), 1, listed)
        for field in ("execution_state", "verification_state", "review_verdict"):
            self.assertIn(field, listed[0], field)
        self.assertEqual(listed[0]["execution_state"], "not-started")


if __name__ == "__main__":
    unittest.main()
