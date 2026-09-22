"""TASK-039: Hooks restore and invalidate from the format 2 store."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
HOOKS = ROOT / "runtime" / "hooks"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import initialize, open_store  # noqa: E402


def run_hook(script: str, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


class TransactionalHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = initialize(self.root)
        self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 0, "action": "goal.create",
            "payload": {"id": "GOAL-001", "title": "Goal"},
        })
        self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 1, "action": "task.create",
            "payload": {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"},
        })
        self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 2, "action": "task.begin",
            "payload": {
                "task_id": "TASK-001", "run_id": "RUN-001",
                "next_action": "verify the artifact",
            },
        })

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_post_tool_use_invalidates_exactly_the_covered_file(self) -> None:
        artifact = self.root / "artifact.txt"
        artifact.write_text("before\n", encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 3, "action": "evidence.record",
            "payload": {
                "id": "EVID-001", "kind": "test", "subject": "artifact",
                "status": "valid", "task_id": "TASK-001",
                "covers": {"files": ["artifact.txt"], "tasks": ["TASK-001"]},
                "version_binding": {"file_hashes": {"artifact.txt": digest}},
            },
        })
        artifact.write_text("after\n", encoding="utf-8")

        result = run_hook("post_tool_use.py", {
            "project_root": str(self.root),
            "tool_name": "apply_patch",
            "path": "artifact.txt",
        })

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EVID-001", result.stdout)
        self.assertEqual(open_store(self.root).get_evidence("EVID-001")["status"], "stale")

    def test_session_restore_reads_goal_task_blocker_evidence_and_next_action(self) -> None:
        self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 3, "action": "task.wait",
            "payload": {
                "task_id": "TASK-001", "kind": "dependency",
                "reason": "upstream task", "resume_when": "upstream completes",
            },
        })
        self.store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": 4, "action": "evidence.record",
            "payload": {
                "id": "EVID-001", "kind": "test", "subject": "task",
                "status": "valid", "task_id": "TASK-001",
                "covers": {"tasks": ["TASK-001"]},
            },
        })

        result = run_hook("session_start.py", {"project_root": str(self.root)})

        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Project goal: GOAL-001", context)
        self.assertIn("Task: TASK-001", context)
        self.assertIn("Blocker: dependency", context)
        self.assertIn("valid=1", context)
        self.assertIn("Next action: Wait for: upstream completes", context)
        self.assertFalse((self.root / ".project-log/loop/active-run.yaml").exists())

    def test_pre_compact_publishes_views_without_legacy_yaml(self) -> None:
        result = run_hook("pre_compact.py", {"project_root": str(self.root)})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hookSpecificOutput", result.stdout)
        self.assertFalse((self.root / ".project-log/loop/handoff.md").exists())
        self.assertTrue((self.root / ".project-log/.state").is_dir())


if __name__ == "__main__":
    unittest.main()
