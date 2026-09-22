"""TASK-059: aligning merges the archived ledger and rebuilds the local SQLite."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
RUNTIME = ROOT / "runtime"
ALIGN = ROOT / "skills" / "a-project-log-align" / "scripts" / "align.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import initialize, open_store  # noqa: E402
from state_ledger import append_event, ledger_path, read_ledger  # noqa: E402


LEDGER_RELATIVE = Path("ledger") / "v1" / "ledger.jsonl"


class AlignSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.kb = self.base / "kb"
        (self.kb / "工程记录").mkdir(parents=True)
        self.work = self.base / "work"
        self.work.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def build_archive(self, actions) -> Path:
        """Build an archived Project Log by running commands through the runtime."""
        source = self.base / "archive-build"
        source.mkdir(exist_ok=True)
        store = initialize(source)
        for action, payload in actions:
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": store.status()["revision"],
                "action": action, "payload": payload,
            })
        destination = self.kb / "工程记录" / "work" / ".project-log"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source / ".project-log", destination)
        return destination

    def seed_local(self, archive: Path, keep: int | None) -> None:
        """Give the work folder the archive marker and at most ``keep`` ledger lines."""
        log = self.work / ".project-log"
        log.mkdir(parents=True, exist_ok=True)
        shutil.copy(archive / "state-format.json", log / "state-format.json")
        (log / ".state").mkdir(exist_ok=True)
        if keep is None:
            return
        lines = (archive / LEDGER_RELATIVE).read_text(encoding="utf-8").splitlines()
        target = log / LEDGER_RELATIVE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines[:keep]) + "\n", encoding="utf-8")

    def align(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = dict(os.environ, VIBE_RUNTIME=str(RUNTIME), VIBE_PYTHON=sys.executable)
        return subprocess.run(
            [sys.executable, str(ALIGN), "--project-root", str(self.work),
             "--kb", str(self.kb), *arguments],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment, check=False,
        )

    def vibe(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "vibe.py"), "--root", str(self.work), *arguments],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )

    def actions(self) -> list[tuple[str, dict]]:
        return [
            ("goal.create", {"id": "GOAL-001", "title": "Goal"}),
            ("task.create", {"id": "TASK-001", "title": "Task", "goal_id": "GOAL-001"}),
            ("task.begin", {"task_id": "TASK-001", "run_id": "RUN-001", "next_action": "work"}),
            ("evidence.record", {
                "id": "EVID-001", "kind": "test", "subject": "task", "status": "valid",
                "task_id": "TASK-001", "covers": {"tasks": ["TASK-001"]},
            }),
            ("task.finish", {"task_id": "TASK-001", "summary": "done"}),
        ]

    def test_align_restores_a_fresh_work_folder_and_rebuilds_sqlite(self) -> None:
        archive = self.build_archive(self.actions())
        self.seed_local(archive, keep=None)

        result = self.align()

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["ledger"]["adopted_from_archive"], 5)
        self.assertEqual(report["validate"], {"errors": []})
        self.assertEqual(report["attach"]["attach"]["appended"], 5)
        merged = read_ledger(self.work / ".project-log" / LEDGER_RELATIVE)
        self.assertEqual(len(merged), 5)
        store = open_store(self.work)
        self.assertEqual(store.get_task("TASK-001")["status"], "implemented-unverified")
        self.assertFalse(store.validate())

    def test_align_keeps_local_only_commands(self) -> None:
        archive = self.build_archive(self.actions())
        self.seed_local(archive, keep=2)
        # The work folder resumes from the truncated archive and adds local work.
        self.assertEqual(self.vibe("state-attach").returncode, 0)
        store = open_store(self.work)
        store.apply({
            "schema_version": 1, "command_id": uuid.uuid4().hex,
            "expected_revision": store.status()["revision"], "action": "record.create",
            "payload": {
                "kind": "research", "id": "RES-001", "title": "Local only",
                "status": "draft",
            },
        })
        local_only = store.status()["revision"]

        result = self.align()

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["ledger"]["adopted_from_archive"], 3)
        self.assertEqual(report["ledger"]["kept_local_only"], 1)
        self.assertEqual(report["ledger"]["merged_events"], 6)
        merged = read_ledger(self.work / ".project-log" / LEDGER_RELATIVE)
        self.assertEqual(len(merged), 6)
        self.assertEqual(merged[-1]["action"], "record.create")
        self.assertEqual(local_only, 3)

    def test_align_dry_run_writes_nothing(self) -> None:
        archive = self.build_archive(self.actions())
        self.seed_local(archive, keep=None)
        before = sorted(
            item.relative_to(self.work).as_posix()
            for item in self.work.rglob("*") if item.is_file()
        )

        result = self.align("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        after = sorted(
            item.relative_to(self.work).as_posix()
            for item in self.work.rglob("*") if item.is_file()
        )
        self.assertEqual(after, before)
        self.assertFalse((self.work / ".project-log" / LEDGER_RELATIVE).exists())

    def test_align_reports_a_missing_archive(self) -> None:
        self.seed_local(self.build_archive(self.actions()), keep=None)
        shutil.rmtree(self.kb / "工程记录" / "work")

        result = self.align()

        self.assertEqual(result.returncode, 1)
        self.assertIn("no archived Project Log", result.stderr)

    def test_align_refuses_a_project_id_mismatch(self) -> None:
        archive = self.build_archive(self.actions())
        self.seed_local(archive, keep=None)
        (self.work / ".project-log" / "state-format.json").write_text(
            json.dumps({"format": 2, "project_id": "f" * 32}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = self.align()

        self.assertEqual(result.returncode, 1)
        self.assertIn("project id mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
