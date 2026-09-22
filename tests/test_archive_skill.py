"""TASK-058: archiving merges the ledger instead of replacing the KB copy."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "a-project-log-archive" / "scripts" / "archive.py"
LEDGER_RELATIVE = Path("ledger") / "v1" / "ledger.jsonl"


def load_archive_module():
    spec = importlib.util.spec_from_file_location("archive_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive_module = load_archive_module()


def event(command_id: str, action: str = "goal.create") -> dict:
    return {
        "schema_version": 1, "command_id": command_id, "origin_kind": "local",
        "origin_context_id": "c" * 64, "origin_revision": 1, "action": action,
        "request": {"command_id": command_id}, "request_hash": "h",
        "receipt": {"command_id": command_id}, "created_at": "2026-01-01T00:00:00+00:00",
        "previous_hash": "", "event_hash": command_id,
    }


def write_ledger(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in events),
        encoding="utf-8",
    )


def read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ArchiveSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.kb = self.base / "kb"
        (self.kb / "工程记录").mkdir(parents=True)
        self.remote = self.base / "kb-remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.kb)], check=True)
        for arguments in (
            ("config", "user.email", "kb@example.invalid"),
            ("config", "user.name", "KB"),
        ):
            subprocess.run(["git", "-C", str(self.kb), *arguments], check=True)
        subprocess.run(["git", "-C", str(self.kb), "remote", "add", "origin", str(self.remote)], check=True)
        (self.kb / "README.md").write_text("kb\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.kb), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.kb), "commit", "-qm", "init"], check=True)
        subprocess.run(
            ["git", "-C", str(self.kb), "push", "-q", "-u", "origin", "HEAD"], check=True,
        )

        self.work = self.base / "work"
        self.log = self.work / ".project-log"
        self.log.mkdir(parents=True)
        self.project_id = uuid.uuid4().hex
        (self.log / "state-format.json").write_text(
            json.dumps({"format": 2, "project_id": self.project_id}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.events = [event("a" * 32), event("b" * 32)]
        write_ledger(self.log / LEDGER_RELATIVE, self.events)
        (self.log / ".state").mkdir()
        (self.log / ".state" / "state.sqlite3").write_bytes(b"sqlite")
        (self.log / "legacy" / "new-writes").mkdir(parents=True)
        (self.log / "legacy" / "new-writes" / "bundle.json").write_text("{}\n", encoding="utf-8")
        (self.log / "docs").mkdir()
        (self.log / "docs" / "note.md").write_text("hello\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def archive(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(self.work), "--kb", str(self.kb)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def commits(self) -> int:
        completed = subprocess.run(
            ["git", "-C", str(self.kb), "rev-list", "--count", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        return int(completed.stdout.strip())

    @property
    def archived(self) -> Path:
        return self.kb / "工程记录" / "work" / ".project-log"

    def test_archive_copies_the_ledger_and_excludes_local_state(self) -> None:
        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.archived / "state-format.json").is_file())
        self.assertEqual(read_ledger(self.archived / LEDGER_RELATIVE), self.events)
        self.assertFalse((self.archived / ".state").exists())
        self.assertFalse((self.archived / "legacy" / "new-writes").exists())
        self.assertTrue((self.archived / "docs" / "note.md").is_file())

    def test_archiving_twice_is_idempotent(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertIn("no-changes", result.stdout)

    def test_archive_appends_only_the_new_tail(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_ledger(self.archived / LEDGER_RELATIVE), self.events)
        self.assertIn('"appended": 1', result.stdout)

    def test_archive_refuses_when_the_knowledge_base_is_ahead(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        # The KB learns about a command the local ledger never saw.
        write_ledger(self.archived / LEDGER_RELATIVE, self.events + [event("d" * 32)])

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("align-project-progress", result.stderr)

    def test_archive_refuses_a_project_id_collision(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        (self.archived / "state-format.json").write_text(
            json.dumps({"format": 2, "project_id": "f" * 32}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("project id mismatch", result.stderr)

    def test_archive_uses_the_work_folder_name(self) -> None:
        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"project": "work"', result.stdout)
        self.assertTrue((self.kb / "工程记录" / "work").is_dir())

    # -- TASK-079: a silent archive must fail loudly ---------------------------------

    def ignore_project_logs(self) -> None:
        """Reproduce the knowledge base rule that hid every format 3 archive."""
        (self.kb / ".gitignore").write_text(".project-log/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.kb), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.kb), "commit", "-qm", "ignore project logs"], check=True
        )

    def remote_ledger(self) -> list[dict]:
        completed = subprocess.run(
            [
                "git", "--git-dir", str(self.remote), "show",
                f"HEAD:工程记录/work/.project-log/{LEDGER_RELATIVE.as_posix()}",
            ],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]

    def test_archive_publishes_new_events_to_the_remote(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_ledger(), self.events)

    def test_archive_refuses_when_the_ledger_is_ignored(self) -> None:
        self.ignore_project_logs()
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("ignores the archived ledger", result.stderr)
        self.assertIn("!工程记录/work/.project-log/", result.stderr)
        self.assertEqual(self.commits(), before)

    def test_archive_accepts_an_ignored_but_already_tracked_ledger(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        self.ignore_project_logs()

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-changes", result.stdout)

    def test_archive_refuses_when_the_index_ledger_is_stale(self) -> None:
        # A skip-worktree entry keeps the index ledger at the old revision while other
        # files still stage, so "something was committed" cannot prove the tail landed.
        self.assertEqual(self.archive().returncode, 0)
        subprocess.run(
            [
                "git", "-C", str(self.kb), "update-index", "--skip-worktree", "--",
                str(self.archived / LEDGER_RELATIVE),
            ],
            check=True,
        )
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from the local ledger", result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertEqual(len(self.remote_ledger()), 2)

    def test_archive_reports_no_changes_when_the_worktree_ledger_was_restored(self) -> None:
        # The committed ledger already matches; restoring a deleted worktree copy is not
        # a new archive tail and must not be misreported as one.
        self.assertEqual(self.archive().returncode, 0)
        (self.archived / LEDGER_RELATIVE).unlink()

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-changes", result.stdout)
        self.assertIn('"appended": 0', result.stdout)

    def test_archive_commit_excludes_unrelated_staged_files(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        (self.kb / "unrelated-secret.txt").write_text("secret\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.kb), "add", "--", "unrelated-secret.txt"], check=True
        )
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        published = subprocess.run(
            ["git", "-C", str(self.kb), "show", "--name-only", "--pretty=format:", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.split()
        self.assertNotIn("unrelated-secret.txt", published)
        still_staged = subprocess.run(
            ["git", "-C", str(self.kb), "diff", "--cached", "--name-only"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertIn("unrelated-secret.txt", still_staged)


if __name__ == "__main__":
    unittest.main()
