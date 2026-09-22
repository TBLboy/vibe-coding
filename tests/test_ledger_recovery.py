"""TASK-062: regression tests for the ledger/projection crash and race defects.

Each test pins one defect that REV-061-NOGO found in the TASK-061 ledger-first
write path: an interleaved writer that outran expected_revision, a read that
reported a stale revision after a crash between the ledger fsync and the SQLite
commit, a cross-context ledger that was mistaken for an in-sync one, an attach
that did not heal a store ahead of an empty ledger, and a retry that returned a
receipt without first repairing a ledger that had rolled back.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import attach, initialize, open_store  # noqa: E402
from state_ledger import (  # noqa: E402
    ledger_path, portability_status, read_ledger, render_ledger, verify_ledger,
)
from state_store import StateError, Store  # noqa: E402


class LedgerRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "work"
        self.root.mkdir()
        self.store = initialize(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def envelope(self, command_id: str, revision: int, action: str, payload: dict) -> dict:
        return {
            "schema_version": 1, "command_id": command_id,
            "expected_revision": revision, "action": action, "payload": payload,
        }

    def goal(self, command_id: str, goal_id: str = "GOAL-001", revision: int | None = None) -> dict:
        return self.envelope(
            command_id, self.store.status()["revision"] if revision is None else revision,
            "goal.create", {"id": goal_id, "title": goal_id},
        )

    def crash_after_append(self):
        """Patch the write path so the process 'dies' right after the ledger fsync."""
        original = Store._ledger_commit

        def commit(store_self, *arguments, **keywords):
            original(store_self, *arguments, **keywords)
            raise RuntimeError("simulated crash after the ledger append")

        return mock.patch.object(Store, "_ledger_commit", commit)

    def test_expected_revision_race_with_live_writer(self) -> None:
        """A writer that observed an old revision loses to the writer that won the lock."""
        entered = threading.Event()
        release = threading.Event()
        original = Store._heal_ledger
        writer_b = open_store(self.root)

        def slow_heal(store_self, connection):
            report = original(store_self, connection)
            if store_self is writer_b:
                entered.set()
                release.wait(10)
            return report

        writer_a = open_store(self.root)
        outcomes: dict = {}

        def run(writer, key, envelope):
            try:
                outcomes[key] = writer.apply(envelope)
            except StateError as error:
                outcomes[key + "_error"] = error

        with mock.patch.object(Store, "_heal_ledger", slow_heal):
            thread_b = threading.Thread(
                target=run,
                args=(writer_b, "b", self.envelope(
                    uuid.uuid4().hex, 0, "goal.create", {"id": "GOAL-B", "title": "B"},
                )),
            )
            thread_b.start()
            self.assertTrue(entered.wait(10), "writer B never entered its write transaction")
            # A stamped the same revision it observed before B committed, but B now
            # holds the write lock. A must wait and then be rejected, not silently
            # apply on top of B with a revision that is no longer current.
            thread_a = threading.Thread(
                target=run,
                args=(writer_a, "a", self.envelope(
                    uuid.uuid4().hex, 0, "goal.create", {"id": "GOAL-A", "title": "A"},
                )),
            )
            thread_a.start()
            time.sleep(0.3)
            release.set()
            thread_b.join(10)
            thread_a.join(10)

        self.assertIn("b", outcomes)
        self.assertNotIn("a", outcomes)
        self.assertEqual(getattr(outcomes.get("a_error"), "code", None), "stale_revision")
        self.assertEqual(writer_b.status()["revision"], 1)
        self.assertEqual(writer_a.status()["revision"], 1)

    def test_status_after_crash_between_ledger_and_sqlite(self) -> None:
        """A read must not report the pre-crash revision once the ledger has the command."""
        with self.crash_after_append():
            with self.assertRaises(RuntimeError):
                self.store.apply(self.goal(uuid.uuid4().hex))

        # The pure store still lags, which is exactly the drift a read must not hide.
        self.assertEqual(open_store(self.root).status()["revision"], 0)

        healed = open_store(self.root, heal=True)
        self.assertEqual(healed.status()["revision"], 1)
        self.assertEqual(healed.active_goal_id(), "GOAL-001")
        self.assertTrue(verify_ledger(self.root, healed)["matches"])

    def test_cross_context_same_origin_revision_tip(self) -> None:
        """A foreign ledger whose tip revision matches is not thereby in sync."""
        other_root = Path(self.temporary.name) / "other"
        other_root.mkdir()
        other = initialize(other_root)
        other.apply(self.envelope(
            uuid.uuid4().hex, 0, "goal.create", {"id": "GOAL-OTHER", "title": "Other"},
        ))
        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-LOCAL"))

        # Both ledgers have one event whose origin_revision is 1, but the command
        # ids differ. The tip revision alone cannot prove the histories match.
        shutil.copy(ledger_path(other_root), ledger_path(self.root))

        with self.assertRaises(StateError) as caught:
            self.store.reconcile_with_ledger()
        self.assertEqual(caught.exception.code, "ledger_diverged")
        # The local store is untouched and a write fails closed instead of
        # committing on top of a foreign ledger.
        self.assertEqual(self.store.status()["revision"], 1)
        self.assertEqual(self.store.active_goal_id(), "GOAL-LOCAL")
        with self.assertRaises(StateError) as write_error:
            self.store.apply(self.envelope(
                uuid.uuid4().hex, 1, "goal.create", {"id": "GOAL-SECOND", "title": "Second"},
            ))
        self.assertEqual(write_error.exception.code, "ledger_diverged")

    def test_attach_heals_store_ahead_of_empty_ledger(self) -> None:
        """A ledger rolled back to empty is re-exported from the surviving store."""
        self.store.apply(self.goal(uuid.uuid4().hex))
        path = ledger_path(self.root)
        path.unlink()

        attached = attach(self.root)

        self.assertEqual(attached.status()["revision"], 1)
        self.assertEqual(len(read_ledger(path)), 1)
        self.assertEqual(attached.active_goal_id(), "GOAL-001")
        self.assertTrue(verify_ledger(self.root, attached)["matches"])

    def test_retry_heals_ledger_behind_store(self) -> None:
        """An idempotent retry repairs a ledger that rolled back before it answers."""
        command_id = uuid.uuid4().hex
        envelope = self.goal(command_id)
        receipt = self.store.apply(envelope)
        path = ledger_path(self.root)
        path.unlink()

        retry = open_store(self.root)
        again = retry.apply(envelope)

        self.assertEqual(again["revision"], receipt["revision"])
        self.assertEqual(retry.status()["revision"], 1)
        self.assertEqual(len(read_ledger(path)), 1)
        self.assertTrue(verify_ledger(self.root, retry)["matches"])

    @staticmethod
    def forge_title(request):
        """Mutate a goal.create request's title while keeping its command id."""
        if request["action"] != "goal.create":
            return None
        request["payload"]["title"] = "forged"
        return request

    def rewrite_ledger_payload(self, mutate) -> None:
        """Re-seal the ledger with a mutated request, keeping every command id."""
        path = ledger_path(self.root)
        entries = [dict(entry) for entry in read_ledger(path)]
        for entry in entries:
            request = json.loads(entry["request_json"])
            updated = mutate(request)
            if updated is not None:
                request = updated
                entry["request_json"] = json.dumps(
                    request, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                )
        path.write_text(render_ledger(entries), encoding="utf-8")

    def test_reconcile_fails_closed_on_same_id_ledger_rewrite(self) -> None:
        """A ledger that rewrites a command under the same id is not in sync."""
        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-001"))
        self.rewrite_ledger_payload(self.forge_title)

        with self.assertRaises(StateError) as caught:
            self.store.reconcile_with_ledger()
        self.assertEqual(caught.exception.code, "history_rewritten")

        # The read path must fail closed as well, not present a clean status.
        with self.assertRaises(StateError) as read_error:
            open_store(self.root, heal=True)
        self.assertEqual(read_error.exception.code, "history_rewritten")

        # A write must fail closed too, not commit on top of a rewritten ledger.
        with self.assertRaises(StateError) as write_error:
            self.store.apply(self.envelope(
                uuid.uuid4().hex, 1, "goal.create", {"id": "GOAL-002", "title": "Second"},
            ))
        self.assertEqual(write_error.exception.code, "history_rewritten")
        self.assertEqual(self.store.status()["revision"], 1)
        self.assertEqual(self.store.get_goal("GOAL-001")["title"], "GOAL-001")

    def test_attach_rebuilds_a_forged_projection_with_matching_ids(self) -> None:
        """attach must replay the ledger, not trust an equal command-id sequence."""
        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-001"))
        connection = sqlite3.connect(self.store.path)
        connection.execute("UPDATE goals SET title = 'forged' WHERE id = 'GOAL-001'")
        connection.commit()
        connection.close()
        self.assertFalse(verify_ledger(self.root, open_store(self.root))["matches"])

        attached = attach(self.root)

        self.assertEqual(attached.get_goal("GOAL-001")["title"], "GOAL-001")
        self.assertTrue(verify_ledger(self.root, attached)["matches"])

    def test_attach_rebuilds_a_tampered_event_row(self) -> None:
        """A corrupted derived event row is rebuilt from the ledger, not trusted."""
        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-001"))
        connection = sqlite3.connect(self.store.path)
        connection.execute("UPDATE events SET action = 'forged.action' WHERE local_sequence = 1")
        connection.commit()
        connection.close()
        # verify_ledger only replays entities; the header mismatch shows up in the audit.
        self.assertTrue(open_store(self.root).validate())

        attached = attach(self.root)

        self.assertFalse(attached.validate())
        self.assertTrue(verify_ledger(self.root, attached)["matches"])
        self.assertEqual(attached.status()["revision"], 1)

    def test_generated_handoff_does_not_claim_a_rewritten_ledger_is_current(self) -> None:
        """The rendered handoff must reflect identity, not just the event count."""
        from state_views import publish

        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-001"))
        self.rewrite_ledger_payload(self.forge_title)

        pure = open_store(self.root)
        result = publish(pure, pure.path.parent / "generated")

        handoff = (Path(result["destination"]) / result["generation"] / "handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("NOT PORTABLE", handoff)
        self.assertNotIn("Ledger is current with the local store", handoff)

    def test_portability_status_rejects_a_foreign_ledger_with_the_same_count(self) -> None:
        """Equal event counts are not evidence that the ledger captures this store."""
        other_root = Path(self.temporary.name) / "other"
        other_root.mkdir()
        other = initialize(other_root)
        other.apply(self.envelope(
            uuid.uuid4().hex, 0, "goal.create", {"id": "GOAL-OTHER", "title": "Other"},
        ))
        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-LOCAL"))
        shutil.copy(ledger_path(other_root), ledger_path(self.root))

        report = portability_status(self.root)

        self.assertEqual(report["ledger_events"], 1)
        self.assertEqual(report["store_revision"], 1)
        self.assertFalse(report["in_sync"])
        self.assertFalse(report["portable"])
        self.assertFalse(report["history_rewritten"])
        self.assertEqual(report["unexported_commands"], 1)

    def test_healing_read_fails_closed_on_a_diverged_ledger(self) -> None:
        """A read must not report a normal status for a store that cannot reconcile."""
        other_root = Path(self.temporary.name) / "other"
        other_root.mkdir()
        other = initialize(other_root)
        other.apply(self.envelope(
            uuid.uuid4().hex, 0, "goal.create", {"id": "GOAL-OTHER", "title": "Other"},
        ))
        self.store.apply(self.goal(uuid.uuid4().hex, "GOAL-LOCAL"))
        shutil.copy(ledger_path(other_root), ledger_path(self.root))

        with self.assertRaises(StateError) as caught:
            open_store(self.root, heal=True)
        self.assertEqual(caught.exception.code, "ledger_diverged")


if __name__ == "__main__":
    unittest.main()
