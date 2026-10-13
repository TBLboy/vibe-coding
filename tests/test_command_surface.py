"""TASK-038: one formal command surface; retired legacy entries are gone."""
from __future__ import annotations

from pathlib import Path
import json
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

from state_context import open_store  # noqa: E402


def run_vibe(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VIBE), "--root", str(root), *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )


class CommandSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        initialized = run_vibe(self.root, "init")
        self.assertEqual(initialized.returncode, 0, initialized.stdout)
        store = open_store(self.root)
        store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 0, "action": "goal.create",
            "payload": {"id": "GOAL-001", "title": "Goal"},
        })
        store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 1, "action": "task.create",
            "payload": {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"},
        })

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_formal_task_command_writes_the_single_store(self) -> None:
        result = run_vibe(
            self.root, "task", "begin", "--task-id", "TASK-001",
            "--run-id", "RUN-001", "--next-action", "implement",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        task = open_store(self.root).get_task("TASK-001")
        self.assertEqual(task["status"], "in-progress")
        self.assertEqual(task["run_id"], "RUN-001")
        self.assertFalse((self.root / ".project-log/tasks/task-list.yaml").exists())

    def test_ledger_list_prints_recent_entries(self) -> None:
        # Reading the ledger used to mean exporting it or opening the JSONL by hand.
        result = run_vibe(self.root, "ledger", "list", "--limit", "2")
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["count"], 2)
        self.assertLessEqual(len(payload["entries"]), 2)
        self.assertIn("action", payload["entries"][-1])

    def test_ledger_list_rejects_an_out_of_range_limit(self) -> None:
        result = run_vibe(self.root, "ledger", "list", "--limit", "0")
        self.assertNotEqual(result.returncode, 0)

    def test_evidence_help_documents_the_json_shapes(self) -> None:
        # The flag help used to say only "JSON object", so the real schema had to
        # be read out of state_store.py to write a record at all.
        result = subprocess.run(
            [sys.executable, str(VIBE), "evidence", "record", "--help"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for token in ("JSON shapes", "file_hashes", "requirements"):
            self.assertIn(token, result.stdout)

    def test_evidence_check_requires_exactly_one_source(self) -> None:
        for arguments in (
            ("state-evidence-check",),
            ("state-evidence-check", "--file", "x.json", "--id", "E-001"),
        ):
            with self.subTest(arguments=arguments):
                result = run_vibe(self.root, *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("exactly one of --file or --id", result.stdout)

    def test_task_update_records_attribution_through_the_formal_entry(self) -> None:
        result = run_vibe(
            self.root, "task", "update", "--task-id", "TASK-001",
            "--implementer", "builder",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        task = open_store(self.root).get_task("TASK-001")
        self.assertEqual(task["extensions"]["implementer"], "builder")
        # No attribution given is a validation error, not a silent no-op.
        empty = run_vibe(self.root, "task", "update", "--task-id", "TASK-001")
        self.assertEqual(empty.returncode, 2, empty.stdout)

    def test_retired_legacy_commands_are_rejected(self) -> None:
        for command in ("render-tasks", "next-id", "migrate"):
            before = sorted(path.relative_to(self.root).as_posix()
                            for path in self.root.rglob("*") if path.is_file())
            result = run_vibe(self.root, command)
            self.assertNotEqual(result.returncode, 0, command)
            after = sorted(path.relative_to(self.root).as_posix()
                           for path in self.root.rglob("*") if path.is_file())
            self.assertEqual(before, after, command)
            self.assertFalse((self.root / ".project-log/tasks/task-list.yaml").exists(), command)

    def test_status_and_validate_are_consistent(self) -> None:
        status = run_vibe(self.root, "status")
        self.assertEqual(status.returncode, 0, status.stdout)
        validate = run_vibe(self.root, "validate")
        self.assertEqual(validate.returncode, 0, validate.stdout)

    def test_goal_cancel_through_the_formal_entry(self) -> None:
        result = run_vibe(self.root, "goal", "cancel", "--id", "GOAL-001",
                          "--reason", "用户确认本阶段不再需要")
        self.assertEqual(result.returncode, 0, result.stdout)
        store = open_store(self.root)
        self.assertEqual(store.get_goal("GOAL-001")["status"], "cancelled")
        self.assertEqual(store.get_task("TASK-001")["status"], "cancelled")
        self.assertEqual(store.active_goal_ids(), [])
        # A missing reason is a validation error, not a silent cancellation.
        missing = run_vibe(self.root, "goal", "cancel", "--id", "GOAL-001")
        self.assertEqual(missing.returncode, 2, missing.stdout)

    def test_workspace_clear_is_two_phase_through_the_cli(self) -> None:
        dry = run_vibe(self.root, "workspace", "clear", "--dry-run", "--reason", "重新规划")
        self.assertEqual(dry.returncode, 0, dry.stdout)
        plan = json.loads(dry.stdout)
        self.assertEqual(plan["affected_goal_ids"], ["GOAL-001"])
        self.assertEqual(plan["affected_task_ids"], ["TASK-001"])
        # The dry run wrote nothing.
        self.assertEqual(open_store(self.root).active_goal_ids(), ["GOAL-001"])

        stale = run_vibe(self.root, "workspace", "clear", "--reason", "x",
                         "--expected-revision", str(plan["revision"] + 5),
                         "--plan-digest", plan["plan_digest"])
        self.assertEqual(stale.returncode, 2, stale.stdout)
        self.assertIn("state_conflict", stale.stdout)

        committed = run_vibe(self.root, "workspace", "clear", "--reason", "重新规划",
                             "--expected-revision", str(plan["revision"]),
                             "--plan-digest", plan["plan_digest"])
        self.assertEqual(committed.returncode, 0, committed.stdout)
        store = open_store(self.root)
        self.assertEqual(store.active_goal_ids(), [])
        self.assertEqual(store.status()["workspace_generation"], 1)

        history = run_vibe(self.root, "workspace", "history")
        self.assertEqual(history.returncode, 0, history.stdout)
        self.assertEqual([goal["status"] for goal in json.loads(history.stdout)["goals"]],
                         ["cancelled"])


class NonProjectSurfaceTests(unittest.TestCase):
    """A directory that is not a Vibe project must fail cleanly, not traceback."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_not_a_project(self, *arguments: str) -> None:
        result = run_vibe(self.root, *arguments)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertIn("not_a_project", result.stdout)

    def test_status_on_an_empty_directory(self) -> None:
        self.assert_not_a_project("status")

    def test_validate_on_an_empty_directory(self) -> None:
        self.assert_not_a_project("validate")

    def test_status_on_a_project_log_without_a_marker(self) -> None:
        (self.root / ".project-log").mkdir()
        self.assert_not_a_project("status")


if __name__ == "__main__":
    unittest.main()
