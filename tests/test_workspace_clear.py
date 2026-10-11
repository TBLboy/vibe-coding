"""V3 PR-02: goal cancellation, workspace clearing and the store-schema upgrade.

Covers the acceptance matrix rows T05-T14: cancellation must not run the completion
gate, a clear must be a two-phase plan/commit with a deterministic batch effect, the
active view must empty while history survives, and a stale executor must not be able
to revive cancelled work.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
import sys

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import _DDL, StateError, Store  # noqa: E402
from state_context import initialize as initialize_project, open_store  # noqa: E402


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "state.sqlite3", uuid.uuid4().hex, "c" * 64)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def apply(self, action: str, payload: dict) -> dict:
        return self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": self.store.status()["revision"],
            "action": action, "payload": payload,
        })

    def assert_error(self, code: str, action: str, payload: dict) -> StateError:
        with self.assertRaises(StateError) as caught:
            self.apply(action, payload)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def goal_with_tasks(self, goal_id: str = "GOAL-001", unmet: bool = False) -> None:
        conditions = [{
            "id": "SC-1",
            "status": "pending" if unmet else "not-applicable",
            "reason": "no user-facing surface in this increment",
        }]
        self.apply("goal.create", {
            "id": goal_id, "title": goal_id,
            "extensions": {
                "risk_level": "high", "implementer": "builder",
                "success_conditions": conditions, "required_evidence": [],
            },
        })
        self.apply("task.create", {
            "id": "TASK-001", "title": "TASK-001", "goal_id": goal_id,
            "extensions": {"risk": "normal", "implementer": "builder"},
        })
        self.apply("task.create", {
            "id": "TASK-002", "title": "TASK-002", "goal_id": goal_id,
            "extensions": {"risk": "normal", "implementer": "builder"},
        })
        self.apply("task.begin", {"task_id": "TASK-002", "run_id": "RUN-002", "next_action": "work"})


class GoalCancelTests(StoreTestCase):
    def test_goal_cancel_closes_the_goal_and_its_open_tasks(self) -> None:
        """T06: one command disposes of the goal and every open child task."""
        self.goal_with_tasks()
        receipt = self.apply("goal.cancel", {
            "id": "GOAL-001", "reason": "用户确认本阶段不再需要",
        })
        self.assertEqual(
            receipt["result"],
            {"goal_id": "GOAL-001", "status": "cancelled",
             "cancelled_task_ids": ["TASK-001", "TASK-002"]},
        )
        self.assertEqual(self.store.get_goal("GOAL-001")["status"], "cancelled")
        self.assertEqual(self.store.get_task("TASK-001")["status"], "cancelled")
        self.assertEqual(self.store.get_task("TASK-002")["run"]["status"], "cancelled")
        self.assertEqual(self.store.active_goal_ids(), [])
        self.assertEqual([task["id"] for task in self.store.status()["tasks"]], [])

    def test_goal_cancel_does_not_run_the_completion_gate(self) -> None:
        """T05: a goal whose success conditions are unmet can still be cancelled.

        The goal is high-risk with a pending success condition, so any completion gate
        would reject it. Cancellation must not consult that gate.
        """
        self.goal_with_tasks(unmet=True)
        self.assertFalse(self.store.evaluate_goal("GOAL-001")["passed"])
        self.apply("goal.cancel", {"id": "GOAL-001", "reason": "abandoned by the user"})
        self.assertEqual(self.store.get_goal("GOAL-001")["status"], "cancelled")

    def test_goal_cancel_refuses_a_terminal_goal(self) -> None:
        """T07: a completed goal is not rewritten into a cancellation."""
        self.apply("goal.create", {
            "id": "GOAL-001", "title": "Goal",
            "extensions": {
                "risk_level": "normal",
                "success_conditions": [{
                    "id": "SC-1", "status": "not-applicable", "reason": "nothing to prove",
                }],
                "required_evidence": [],
            },
        })
        self.apply("goal.complete", {"id": "GOAL-001"})
        error = self.assert_error("state_conflict", "goal.cancel",
                                  {"id": "GOAL-001", "reason": "too late"})
        self.assertIn("complete", str(error))
        self.assertEqual(self.store.get_goal("GOAL-001")["status"], "complete")

    def test_goal_cancel_requires_a_reason(self) -> None:
        self.goal_with_tasks()
        self.assert_error("invalid_input", "goal.cancel", {"id": "GOAL-001", "reason": "  "})

    def test_cancelled_work_cannot_be_revived(self) -> None:
        """T13: an executor holding an old task id cannot bring it back to life.

        The state machine is the fence: ``task.begin`` only accepts ``ready`` and
        ``task.resume`` only accepts the paused states, so cancelled work stays gone
        even though the id is still addressable.
        """
        self.goal_with_tasks()
        self.apply("goal.cancel", {"id": "GOAL-001", "reason": "cancelled"})
        self.assert_error("state_conflict", "task.begin",
                          {"task_id": "TASK-001", "run_id": "RUN-009", "next_action": "work"})
        self.assert_error("state_conflict", "task.resume",
                          {"task_id": "TASK-002", "next_action": "work"})
        self.assertEqual(self.store.get_task("TASK-002")["status"], "cancelled")


class WorkspaceClearTests(StoreTestCase):
    def test_workspace_plan_is_read_only(self) -> None:
        """T08: the dry run reports the full set and changes nothing."""
        self.goal_with_tasks()
        revision = self.store.status()["revision"]
        plan = self.store.workspace_plan()
        self.assertEqual(plan["affected_goal_ids"], ["GOAL-001"])
        self.assertEqual(plan["affected_task_ids"], ["TASK-001", "TASK-002"])
        self.assertEqual(plan["active_run_ids"], ["RUN-002"])
        self.assertEqual(plan["revision"], revision)
        self.assertEqual(len(plan["plan_digest"]), 64)
        self.assertTrue(plan["warnings"], plan)
        self.assertEqual(self.store.status()["revision"], revision)

    def test_workspace_clear_rejects_a_stale_plan(self) -> None:
        """T09: a plan digest from another revision must not clear anything."""
        self.goal_with_tasks()
        plan = self.store.workspace_plan()
        self.apply("task.create", {
            "id": "TASK-003", "title": "TASK-003", "goal_id": "GOAL-001",
            "extensions": {"risk": "normal", "implementer": "builder"},
        })
        error = self.assert_error("plan_mismatch", "workspace.clear",
                                  {"reason": "stale", "plan_digest": plan["plan_digest"]})
        self.assertIn("plan digest", str(error))
        self.assertEqual(self.store.active_goal_ids(), ["GOAL-001"])

    def test_workspace_clear_empties_the_view_and_keeps_history(self) -> None:
        """T10/T11: the active view empties; every old record stays queryable."""
        self.goal_with_tasks()
        plan = self.store.workspace_plan()
        receipt = self.apply("workspace.clear", {
            "reason": "重新规划", "plan_digest": plan["plan_digest"],
        })
        self.assertEqual(
            receipt["result"],
            {"cleared": True, "generation_before": 0, "generation_after": 1,
             "cancelled_goal_ids": ["GOAL-001"],
             "cancelled_task_ids": ["TASK-001", "TASK-002"]},
        )
        self.assertEqual(self.store.active_goal_ids(), [])
        self.assertEqual([task["id"] for task in self.store.status()["tasks"]], [])
        self.assertEqual(self.store.status()["workspace_generation"], 1)
        history = self.store.workspace_history()
        self.assertEqual([(goal["id"], goal["status"]) for goal in history["goals"]],
                         [("GOAL-001", "cancelled")])
        self.assertEqual([task["id"] for task in history["tasks"]],
                         ["TASK-001", "TASK-002"])

    def test_workspace_clear_is_idempotent_when_nothing_is_active(self) -> None:
        """T12: clearing an empty workspace is a no-op, not a new generation."""
        self.goal_with_tasks()
        self.apply("workspace.clear", {
            "reason": "first", "plan_digest": self.store.workspace_plan()["plan_digest"],
        })
        plan = self.store.workspace_plan()
        receipt = self.apply("workspace.clear", {
            "reason": "again", "plan_digest": plan["plan_digest"],
        })
        self.assertEqual(receipt["result"], {
            "cleared": False, "generation_before": 1, "generation_after": 1,
            "cancelled_goal_ids": [], "cancelled_task_ids": [],
        })
        self.assertEqual(self.store.status()["workspace_generation"], 1)


    def test_forged_authorization_fields_do_not_authorize_a_clear(self) -> None:
        """T32: a payload cannot grant itself permission to clear the workspace.

        Bulk clearing is a management action that the host authorizes; the store has no
        identity of its own to check a caller against. What it can guarantee is the
        negative: a payload asserting its own authority (`actor`, `authorized_by`, ...)
        is an unknown field and is rejected, never read as consent.
        """
        self.goal_with_tasks()
        plan = self.store.workspace_plan()
        for forged in ({"actor": "user"}, {"authorized_by": "human"}, {"approved": True}):
            payload = {"reason": "bulk clear", "plan_digest": plan["plan_digest"]}
            payload.update(forged)
            error = self.assert_error("invalid_input", "workspace.clear", payload)
            self.assertIn("unknown fields", str(error))
        self.assertEqual(self.store.active_goal_ids(), ["GOAL-001"])


class WorkspaceRecoveryTests(unittest.TestCase):
    def test_clear_survives_the_crash_between_ledger_and_projection(self) -> None:
        """T14: the ledger is authoritative, so a lost SQLite commit is repaired.

        The store file is rewound to its pre-clear bytes to stand in for a crash after
        the ledger fsync but before the SQLite commit; healing must replay the clear.
        """
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            initialize_project(project)
            store = open_store(project)
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.create",
                "payload": {"id": "GOAL-001", "title": "Goal"},
            })
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "task.create",
                "payload": {
                    "id": "TASK-001", "title": "Task", "goal_id": "GOAL-001",
                    "extensions": {"risk": "normal", "implementer": "builder"},
                },
            })
            before = store.path.read_bytes()
            revision_before = store.status()["revision"]

            open_store(project).apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": revision_before, "action": "workspace.clear",
                "payload": {
                    "reason": "replan", "plan_digest": open_store(project).workspace_plan()["plan_digest"],
                },
            })
            self.assertEqual(open_store(project).active_goal_ids(), [])

            store.path.write_bytes(before)

            healed = open_store(project, heal=True)
            self.assertEqual(healed.active_goal_ids(), [])
            self.assertEqual(healed.get_goal("GOAL-001")["status"], "cancelled")
            self.assertEqual(healed.status()["workspace_generation"], 1)
            self.assertEqual(healed.validate(), [])


class StoreUpgradeTests(unittest.TestCase):
    def test_upgrade_rebuilds_a_store_written_by_schema_three(self) -> None:
        """A schema-3 store is migrated in place, keeping its rows and accepting cancel."""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.sqlite3"
            project_id, context_id = uuid.uuid4().hex, "c" * 64
            old_ddl = [
                statement
                .replace("CHECK(store_schema = 4)", "CHECK(store_schema = 3)")
                .replace("'complete','cancelled'", "'complete'")
                for statement in _DDL
            ]
            connection = sqlite3.connect(str(path))
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN IMMEDIATE")
            for statement in old_ddl:
                connection.execute(statement)
            connection.execute("INSERT INTO metadata VALUES (1, 3, 1, ?, ?, 0)",
                               (project_id, context_id))
            connection.execute("INSERT INTO projection_jobs VALUES (1, 0)")
            connection.execute("INSERT INTO exchange VALUES (1, NULL, 0, NULL, NULL, NULL, NULL)")
            connection.execute(
                "INSERT INTO goals VALUES ('GOAL-001', 'Goal', 'active', '{}', 1, 1)"
            )
            connection.commit()
            connection.close()

            store = Store(path, project_id, context_id)
            report = store.upgrade()
            self.assertEqual(report, {"status": "upgraded", "store_schema": 4})
            self.assertEqual(store.get_goal("GOAL-001")["status"], "active")
            self.assertEqual(store.upgrade(), {"status": "current", "store_schema": 4})
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"], "action": "goal.cancel",
                "payload": {"id": "GOAL-001", "reason": "not needed"},
            })
            self.assertEqual(store.get_goal("GOAL-001")["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
