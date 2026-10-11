"""TASK-061: the ledger append is the commit point; SQLite is a healable projection."""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import attach, initialize, open_store  # noqa: E402
from state_ledger import ledger_path, read_ledger, verify_ledger  # noqa: E402
from state_store import StateError, Store  # noqa: E402


class LedgerFirstWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = initialize(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def envelope(self, command_id: str, revision: int, action: str, payload: dict) -> dict:
        return {
            "schema_version": 1, "command_id": command_id,
            "expected_revision": revision, "action": action, "payload": payload,
        }

    def goal(self, command_id: str | None = None) -> dict:
        return self.envelope(
            command_id or uuid.uuid4().hex, self.store.status()["revision"],
            "goal.create", {"id": "GOAL-001", "title": "Goal"},
        )

    def crash_after_append(self):
        """Patch the write path so the process 'dies' right after the ledger fsync."""
        original = Store._ledger_commit

        def commit(store_self, *arguments, **keywords):
            original(store_self, *arguments, **keywords)
            raise RuntimeError("simulated crash after the ledger append")

        return mock.patch.object(Store, "_ledger_commit", commit)

    def test_crash_before_the_ledger_append_leaves_no_command(self) -> None:
        with mock.patch.object(
            Store, "_ledger_commit", side_effect=RuntimeError("simulated crash")
        ):
            with self.assertRaises(RuntimeError):
                self.store.apply(self.goal())

        self.assertEqual(read_ledger(ledger_path(self.root)), [])
        reopened = open_store(self.root)
        self.assertEqual(reopened.status()["revision"], 0)
        self.assertFalse(reopened.validate())

    def test_crash_before_the_transition_leaves_no_command(self) -> None:
        with mock.patch.object(
            Store, "_transition", side_effect=RuntimeError("simulated crash")
        ):
            with self.assertRaises(RuntimeError):
                self.store.apply(self.goal())

        self.assertEqual(read_ledger(ledger_path(self.root)), [])
        self.assertEqual(open_store(self.root).status()["revision"], 0)

    def test_crash_after_the_ledger_append_reconciles_on_restart(self) -> None:
        command_id = uuid.uuid4().hex
        with self.crash_after_append():
            with self.assertRaises(RuntimeError):
                self.store.apply(self.goal(command_id))

        # The ledger is ahead of the projection: the command is durable but the
        # SQLite transaction rolled back.
        entries = read_ledger(ledger_path(self.root))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["command_id"], command_id)
        self.assertEqual(open_store(self.root).status()["revision"], 0)

        # Restart: attach replays the missing tail, so the state is self-consistent.
        attached = attach(self.root)
        self.assertEqual(attached.status()["revision"], 1)
        self.assertEqual(attached.active_goal_id(), "GOAL-001")
        self.assertTrue(verify_ledger(self.root, attached)["matches"])
        self.assertFalse(attached.validate())

    def test_apply_heals_a_projection_that_lags_the_ledger(self) -> None:
        with self.crash_after_append():
            with self.assertRaises(RuntimeError):
                self.store.apply(self.goal())

        # A read heals the projection: the command is already durable in the ledger,
        # so reporting the pre-crash revision would be a silent lie.
        reopened = open_store(self.root, heal=True)
        self.assertEqual(reopened.status()["revision"], 1)

        # A write stamped with the stale revision is rejected, because the ledger
        # commit already happened and another observer could have seen it.
        with self.assertRaises(StateError) as caught:
            reopened.apply(self.envelope(
                uuid.uuid4().hex, 0, "goal.create", {"id": "GOAL-002", "title": "Second"},
            ))
        self.assertEqual(caught.exception.code, "stale_revision")

        # Re-stamping with the healed revision applies on top of the recovered state.
        reopened.apply(self.envelope(
            uuid.uuid4().hex, 1, "goal.create", {"id": "GOAL-002", "title": "Second"},
        ))

        self.assertEqual(reopened.status()["revision"], 2)
        # The heal/retry path leaves two active goals behind (GOAL-002 applied on top
        # of the recovered GOAL-001); the default target now refuses to pick one, so
        # the assertion names the full set instead of relying on the old earliest-wins rule.
        self.assertEqual(reopened.active_goal_ids(), ["GOAL-001", "GOAL-002"])
        self.assertTrue(verify_ledger(self.root, reopened)["matches"])

    def test_retrying_the_same_command_after_a_crash_is_idempotent(self) -> None:
        command_id = uuid.uuid4().hex
        with self.crash_after_append():
            with self.assertRaises(RuntimeError):
                self.store.apply(self.goal(command_id))

        # The real write path is restored; retrying the identical envelope heals the
        # projection and returns the receipt that the crashed attempt never returned.
        reopened = open_store(self.root)
        receipt = reopened.apply(self.goal(command_id))

        self.assertEqual(receipt["command_id"], command_id)
        self.assertEqual(reopened.status()["revision"], 1)
        self.assertEqual(len(read_ledger(ledger_path(self.root))), 1)

    def test_crash_after_both_commits_is_consistent(self) -> None:
        receipt = self.store.apply(self.goal())

        self.assertEqual(receipt["revision"], 1)
        self.assertEqual(len(read_ledger(ledger_path(self.root))), 1)
        reopened = open_store(self.root)
        self.assertEqual(reopened.status()["revision"], 1)
        self.assertTrue(verify_ledger(self.root, reopened)["matches"])

    def test_a_partial_trailing_write_is_discarded_before_the_next_append(self) -> None:
        # A process killed mid-write can leave half a line; that command was never
        # committed, so the next append truncates it and keeps the chain valid.
        self.store.apply(self.goal())
        path = ledger_path(self.root)
        good = path.read_text(encoding="utf-8")
        path.write_text(good + '{"schema_version":1,"command_id":"trunc', encoding="utf-8")

        self.assertEqual(open_store(self.root).status()["revision"], 1)
        self.store.apply(self.envelope(
            uuid.uuid4().hex, 1, "goal.create", {"id": "GOAL-002", "title": "Second"},
        ))

        self.assertTrue(path.read_text(encoding="utf-8").startswith(good))
        self.assertNotIn("trunc", path.read_text(encoding="utf-8"))
        entries = read_ledger(path)
        self.assertEqual(len(entries), 2)
        self.assertTrue(verify_ledger(self.root, open_store(self.root))["matches"])


if __name__ == "__main__":
    unittest.main()
