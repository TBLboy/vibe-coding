"""Project Log format 2 default initialization: BL-FRAMELAND-001 (AC-FL-001, AC-FL-002)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = SCRIPTS / "vibe.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import read_marker  # noqa: E402


LEGACY_ENTRIES = (
    ".project-log/workflow.yaml",
    ".project-log/tasks/task-list.yaml",
    ".project-log/loop/active-run.yaml",
    ".project-log/goals/active-goal.yaml",
)

SEED_ENTRIES = (
    ".project-log/current-session.md",
    ".project-log/progress.md",
    ".project-log/docs/archive/README.md",
)


def run_vibe(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(VIBE), *arguments],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class ProjectLogInitTests(unittest.TestCase):
    def test_fresh_directory_defaults_to_format_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)

            result = run_vibe("--root", str(target), "init")

            self.assertEqual(result.returncode, 0, result.stdout)
            marker_path = target / ".project-log/state-format.json"
            self.assertTrue(marker_path.is_file(), result.stdout)
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual(marker["format"], 2)
            self.assertNotIn("experimental", marker)
            for relative in SEED_ENTRIES:
                self.assertTrue((target / relative).is_file(), relative)
            for relative in LEGACY_ENTRIES:
                self.assertFalse((target / relative).exists(), relative)
            self.assertIn(".state/", (target / ".project-log/.gitignore").read_text(encoding="utf-8"))

    def test_new_format_two_project_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            self.assertEqual(run_vibe("--root", str(target), "init").returncode, 0)

            result = run_vibe("--root", str(target), "validate")

            self.assertEqual(result.returncode, 0, result.stdout)

    def test_existing_project_log_is_skipped_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            log = target / ".project-log"
            log.mkdir()
            kept = log / "notes.md"
            kept.write_text("keep me\n", encoding="utf-8")

            result = run_vibe("--root", str(target), "init")

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("skipped", result.stdout)
            self.assertEqual(kept.read_text(encoding="utf-8"), "keep me\n")
            self.assertFalse((log / "state-format.json").exists())

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)

            result = run_vibe("--root", str(target), "init", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse((target / ".project-log").exists())

    def test_state_init_alias_needs_no_experimental_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)

            result = run_vibe("--root", str(target), "state-init")

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((target / ".project-log/state-format.json").is_file())

    def test_pre_promotion_marker_is_still_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            self.assertEqual(run_vibe("--root", str(target), "init").returncode, 0)
            marker_path = target / ".project-log/state-format.json"
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["experimental"] = True
            marker_path.write_text(json.dumps(marker) + "\n", encoding="utf-8")

            self.assertEqual(read_marker(target)["format"], 2)

    def test_marker_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            self.assertEqual(run_vibe("--root", str(target), "init").returncode, 0)
            marker_path = target / ".project-log/state-format.json"
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["unexpected"] = True
            marker_path.write_text(json.dumps(marker) + "\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                read_marker(target)

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_init_outside_the_worktree_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            nested = workspace / "nested"
            nested.mkdir()

            result = run_vibe("--root", str(nested), "init")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Git worktree root", result.stdout)
            self.assertFalse((nested / ".project-log").exists())

    def test_plain_work_directory_ignores_an_empty_ancestor_git_directory(self) -> None:
        """An empty stray `.git` is not a repository and must not block init.

        A plain work directory is the supported layout for a Project Log that owns
        nested repositories, so an aborted `git init` in a parent directory (a
        common accident in a home directory) cannot be allowed to abort every
        command with a git_context_error.
        """
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / ".git").mkdir()
            work = workspace / "work"
            work.mkdir()

            result = run_vibe("--root", str(work), "init")

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((work / ".project-log/state-format.json").is_file())
            status = run_vibe("--root", str(work), "status")
            self.assertEqual(status.returncode, 0, status.stdout)

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_plain_work_directory_keeps_the_log_outside_a_nested_repository(self) -> None:
        """The work directory owns the log; the nested code repository stays separate."""
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / "work"
            repository = work / "code"
            repository.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)

            result = run_vibe("--root", str(work), "init")

            self.assertEqual(result.returncode, 0, result.stdout)
            # The log lives beside the repository, and the repository does not track it.
            self.assertTrue((work / ".project-log/state-format.json").is_file())
            self.assertFalse((repository / ".project-log").exists())
            tracked = subprocess.run(
                ["git", "-C", str(repository), "status", "--porcelain"],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout
            self.assertNotIn("project-log", tracked)
            # A non-Git work directory keeps its SQLite cache inside the Project Log.
            self.assertTrue((work / ".project-log" / ".state").is_dir())


if __name__ == "__main__":
    unittest.main()
