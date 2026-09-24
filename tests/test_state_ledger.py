"""TASK-049: export the command history to the Git-tracked Project Log ledger."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import attach, initialize  # noqa: E402
from state_ledger import (  # noqa: E402
    LEDGER_RELATIVE, LEDGER_TEMP_SUFFIX, export_ledger, ledger_path, portability_status,
    read_ledger, render_ledger, verify_ledger,
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
        # Ledger-first writes already produced the ledger, so exporting is a no-op
        # and re-exporting never rewrites the bytes.
        path = self.root / LEDGER_RELATIVE
        first = export_ledger(self.store)
        original = path.read_bytes()

        second = export_ledger(self.store)

        self.assertTrue(first["unchanged"])
        self.assertTrue(second["unchanged"])
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(path.read_bytes(), original)

    def test_export_rebuilds_a_deleted_ledger(self) -> None:
        self.build()
        path = self.root / LEDGER_RELATIVE
        expected = path.read_bytes()
        path.unlink()

        result = export_ledger(self.store)

        self.assertFalse(result["unchanged"])
        self.assertEqual(path.read_bytes(), expected)

    def test_ledger_rewrite_cleans_up_and_ignores_its_temporary(self) -> None:
        """A killed rewrite must not leave a file that `git add -A` could stage."""
        self.build()
        path = self.root / LEDGER_RELATIVE
        path.unlink()  # force a real rewrite

        result = export_ledger(self.store)

        self.assertFalse(result["unchanged"])
        self.assertTrue(path.is_file())
        ledger_directory = path.parent
        self.assertEqual(
            list(ledger_directory.glob("*.tmp*")), [], "a temporary file was left behind"
        )
        ignore = ledger_directory / ".gitignore"
        self.assertTrue(ignore.is_file(), "the ledger directory has no ignore rule")
        self.assertIn(".tmp-", ignore.read_text(encoding="utf-8"))

        # The rule must actually cover a leftover orphan, not merely exist.
        orphan = ledger_directory / f"{path.name}{LEDGER_TEMP_SUFFIX}deadbeef"
        orphan.write_text("orphan\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        checked = subprocess.run(
            ["git", "-C", str(self.root), "check-ignore", "-q",
             str(orphan.relative_to(self.root))],
            capture_output=True,
        )
        self.assertEqual(checked.returncode, 0, "git does not ignore the leftover temporary file")

    def test_ledger_ignore_rule_is_appended_to_an_existing_gitignore(self) -> None:
        """A ledger directory that already carries a .gitignore still gets the rule."""
        self.build()
        path = self.root / LEDGER_RELATIVE
        ledger_directory = path.parent
        ledger_directory.mkdir(parents=True, exist_ok=True)
        ignore = ledger_directory / ".gitignore"
        ignore.write_text("# user rule\n*.bak\n", encoding="utf-8")
        path.unlink()

        export_ledger(self.store)

        contents = ignore.read_text(encoding="utf-8")
        self.assertIn("*.bak", contents, "the existing rule was lost")
        self.assertIn(f"*{LEDGER_TEMP_SUFFIX}*", contents, "the ignore rule was not appended")
        # Running again must not duplicate the rule.
        path.unlink()
        export_ledger(self.store)
        self.assertEqual(
            ignore.read_text(encoding="utf-8").count(f"*{LEDGER_TEMP_SUFFIX}*"), 1,
            "the ignore rule was appended twice",
        )

    def test_interrupted_ledger_rewrite_leaves_no_temporary_behind(self) -> None:
        self.build()
        elsewhere = ledger_path(self.root).with_name("other-ledger.jsonl")

        with mock.patch("state_ledger.os.replace", side_effect=OSError("killed mid-rewrite")):
            with self.assertRaises(OSError):
                export_ledger(self.store, path=elsewhere)

        # The rename never ran, so the target is untouched and the temporary file
        # the rewrite wrote is cleaned up instead of being left beside it. The glob
        # covers any temporary naming, so it also fails if the cleanup disappears.
        self.assertFalse(elsewhere.exists())
        self.assertEqual(list(elsewhere.parent.glob("*.tmp*")), [])

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

    def test_ledger_hash_chain_rejects_tampering(self) -> None:
        self.build()
        export_ledger(self.store)
        path = self.root / LEDGER_RELATIVE
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

        tampered = json.loads(lines[1])
        tampered["action"] = "task.cancel"
        lines[1] = json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with self.assertRaises(StateError):
            read_ledger(path)

        # Dropping an event must also break the chain rather than silently renumbering.
        path.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
        with self.assertRaises(StateError):
            read_ledger(path)

    def test_ledger_path_is_project_local(self) -> None:
        self.assertEqual(
            ledger_path(self.root),
            (self.root / ".project-log" / "ledger" / "v1" / "ledger.jsonl").resolve(),
        )

    def clone(self, name: str) -> Path:
        """A clean clone: same marker and ledger, no local .state/ SQLite."""
        destination = self.root / name
        log = destination / ".project-log"
        log.mkdir(parents=True)
        shutil.copy(
            self.root / ".project-log" / "state-format.json",
            log / "state-format.json",
        )
        shutil.copytree(self.root / ".project-log" / "ledger", log / "ledger")
        return destination

    def entities(self, store) -> dict:
        with store._connection() as connection:
            return store._entity_rows(connection)

    def test_attach_rebuilds_a_clean_clone_from_the_ledger(self) -> None:
        self.build()
        export_ledger(self.store)

        clone = self.clone("clone-a")
        attached = attach(clone)

        self.assertEqual(self.entities(attached), self.live())
        self.assertEqual(attached.status()["revision"], self.store.status()["revision"])

    def test_reconcile_is_identical_when_the_store_already_matches(self) -> None:
        self.build()
        export_ledger(self.store)
        attached = attach(self.clone("clone-b"))

        entries = read_ledger(ledger_path(attached.root))
        report = attached.sync_from_ledger(entries)

        self.assertEqual(report["status"], "identical")
        self.assertEqual(report["appended"], 0)

    def test_reconcile_appends_events_the_clone_has_not_seen(self) -> None:
        self.build()
        export_ledger(self.store)
        clone = self.clone("clone-c")
        attached = attach(clone)

        self.apply("record.create", {
            "kind": "research", "id": "RES-001", "title": "Later work",
            "status": "draft", "payload": {"summary": "added after clone"},
        })
        export_ledger(self.store)
        # A clone learns about new history by pulling the updated ledger file.
        shutil.copy(self.root / LEDGER_RELATIVE, clone / LEDGER_RELATIVE)

        entries = read_ledger(ledger_path(clone))
        report = attached.sync_from_ledger(entries)

        self.assertEqual(report["status"], "appended")
        self.assertEqual(report["appended"], 1)
        self.assertEqual(self.entities(attached), self.live())

    def test_reconcile_rebuilds_a_diverged_projection(self) -> None:
        self.build()
        export_ledger(self.store)
        clone = self.clone("clone-d")
        attached = attach(clone)

        connection = sqlite3.connect(attached.path)
        connection.execute("UPDATE tasks SET title = 'forged' WHERE id = 'TASK-001'")
        connection.commit()
        connection.close()

        entries = read_ledger(ledger_path(clone))
        report = attached.sync_from_ledger(entries)

        self.assertEqual(report["status"], "rebuilt")
        self.assertEqual(self.entities(attached), self.live())

    def test_reconcile_refuses_when_the_ledger_is_behind(self) -> None:
        self.build()
        export_ledger(self.store)
        stale = read_ledger(ledger_path(self.root))

        self.apply("record.create", {
            "kind": "research", "id": "RES-002", "title": "Local only",
            "status": "draft", "payload": {"summary": "not yet exported"},
        })

        with self.assertRaises(StateError):
            self.store.sync_from_ledger(stale)

    def test_portability_status_is_true_when_ledger_is_current(self) -> None:
        self.build()
        export_ledger(self.store)

        report = portability_status(self.root)

        self.assertTrue(report["in_sync"])
        self.assertTrue(report["portable"])
        self.assertEqual(report["unexported_commands"], 0)
        self.assertIsNone(report["git"])

    def test_portability_status_reports_a_ledger_that_lags_the_store(self) -> None:
        self.build()
        # Simulate a ledger that has not yet captured the newest command: dropping
        # the trailing event leaves a valid prefix that is one revision behind.
        path = self.root / LEDGER_RELATIVE
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

        report = portability_status(self.root)

        self.assertFalse(report["in_sync"])
        self.assertFalse(report["portable"])
        self.assertEqual(report["unexported_commands"], 1)


if __name__ == "__main__":
    unittest.main()
