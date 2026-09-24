"""TASK-038: one formal command surface; retired legacy entries are gone."""
from __future__ import annotations

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
