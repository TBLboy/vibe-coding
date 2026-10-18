"""V3 PR-06: restoring a session must not revive work that was cleared away.

Acceptance rows T13/T31 and the release gate: after `workspace.clear` the active view is
empty while history survives, a session or executor still holding the pre-clear view
cannot write into the new generation, and a cancelled goal is never silently chosen as
the default target.
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
from state_context import compact_context, initialize, open_store  # noqa: E402


class SessionRecoveryTests(unittest.TestCase):
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

    def build_active_workspace(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("task.create", {"id": "TASK-1", "title": "Work", "goal_id": "GOAL-1"})
        self.apply("task.begin", {
            "task_id": "TASK-1", "run_id": "RUN-1", "next_action": "implement",
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]
        })

    def clear_workspace(self, reason: str = "user asked to clear") -> dict:
        plan = self.store.workspace_plan()
        return self.apply("workspace.clear", {
            "reason": reason, "plan_digest": plan["plan_digest"],
        })

    def test_a_restored_session_does_not_see_pre_clear_work(self) -> None:
        self.build_active_workspace()
        self.clear_workspace()

        restored = open_store(self.root)
        state = restored.status()
        self.assertEqual(state["workspace_generation"], 1)
        self.assertEqual(state["tasks"], [])
        self.assertIsNone(state["current_run"])
        self.assertIsNone(state["current_task"])
        self.assertEqual(restored.active_goal_ids(), [])

    def test_a_stale_executor_cannot_write_into_the_new_generation(self) -> None:
        """T13: the pre-clear task is cancelled, so no old executor can resume it."""
        self.build_active_workspace()
        self.clear_workspace()

        restored = open_store(self.root)
        for action, payload in (
            ("task.begin", {"task_id": "TASK-1", "run_id": "RUN-OLD", "next_action": "revive",
            "owner": "test-agent", "session_id": "test-session", "write_scope": ["."]}),
            ("task.resume", {"task_id": "TASK-1", "next_action": "revive"}),
            ("task.finish", {"task_id": "TASK-1", "summary": "revived"}),
        ):
            with self.assertRaises(StateError) as caught:
                restored.apply({
                    "schema_version": 1, "command_id": uuid.uuid4().hex,
                    "expected_revision": restored.status()["revision"],
                    "action": action, "payload": payload,
                })
            self.assertEqual(caught.exception.code, "state_conflict", action)
        self.assertEqual(restored.status()["tasks"], [])

    def test_a_stale_fencing_token_is_rejected_after_a_clear(self) -> None:
        """T13: a writer that names the pre-clear generation is refused outright.

        Cancelling the old task stops an executor from reviving it, but an executor that
        restored the pre-clear view could still create *new* work in the generation it
        believes is current. The fencing token closes that: a write that names the
        generation the writer really saw is checked against the generation on disk.
        """
        self.build_active_workspace()
        self.clear_workspace()

        restored = open_store(self.root)
        with self.assertRaises(StateError) as caught:
            restored.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": restored.status()["revision"],
                "expected_generation": 0,
                "action": "goal.create",
                "payload": {"id": "GOAL-OLD", "title": "Revived work"},
            })
        self.assertEqual(caught.exception.code, "state_conflict")
        self.assertIn("generation", str(caught.exception))
        self.assertEqual(restored.active_goal_ids(), [])
        self.assertEqual(restored.status()["workspace_generation"], 1)

    def test_the_current_fencing_token_is_accepted(self) -> None:
        """The fence must not block a writer that names the generation it really saw."""
        self.build_active_workspace()
        self.clear_workspace()

        restored = open_store(self.root)
        restored.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": restored.status()["revision"],
            "expected_generation": 1,
            "action": "goal.create",
            "payload": {"id": "GOAL-NEW", "title": "New work"},
        })
        self.assertEqual(restored.active_goal_ids(), ["GOAL-NEW"])

    def test_history_keeps_everything_the_active_view_dropped(self) -> None:
        self.build_active_workspace()
        self.clear_workspace()

        history = open_store(self.root).workspace_history()
        self.assertEqual([goal["id"] for goal in history["goals"]], ["GOAL-1"])
        self.assertEqual(history["goals"][0]["status"], "cancelled")
        self.assertEqual(
            sorted(task["id"] for task in history["tasks"]), ["TASK-1"],
        )
        self.assertEqual(history["tasks"][0]["status"], "cancelled")

    def test_the_restore_context_reports_the_generation(self) -> None:
        self.build_active_workspace()
        self.clear_workspace()

        context = compact_context(self.root)
        self.assertIn("Workspace generation: 1", context)
        # The restore text must not present cleared work as the current task.
        self.assertNotIn("TASK-1", context)

    def test_a_cancelled_goal_is_never_the_default_target(self) -> None:
        self.apply("goal.create", {"id": "GOAL-1", "title": "Goal"})
        self.apply("goal.cancel", {"id": "GOAL-1", "reason": "not needed"})
        restored = open_store(self.root)
        self.assertEqual(restored.active_goal_ids(), [])
        with self.assertRaises(StateError) as caught:
            restored.active_goal_id()
        self.assertEqual(caught.exception.code, "not_found")

    def test_several_active_goals_are_refused_instead_of_guessed(self) -> None:
        """T31: with more than one current goal, the default target stays ambiguous."""
        self.apply("goal.create", {"id": "GOAL-1", "title": "First"})
        self.apply("goal.create", {"id": "GOAL-2", "title": "Second"})
        restored = open_store(self.root)
        self.assertEqual(sorted(restored.active_goal_ids()), ["GOAL-1", "GOAL-2"])
        with self.assertRaises(StateError) as caught:
            restored.active_goal_id()
        self.assertEqual(caught.exception.code, "state_conflict")
        context = compact_context(self.root)
        self.assertIn("ambiguous", context)
        self.assertIn("GOAL-1", context)
        self.assertIn("GOAL-2", context)


if __name__ == "__main__":
    unittest.main()
