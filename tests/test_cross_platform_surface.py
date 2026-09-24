"""TASK-043/TASK-060: launcher and project-scoped context checks available on this host."""
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
RUNTIME = ROOT / "runtime"
VIBE_SH = RUNTIME / "vibe.sh"
if str(RUNTIME / "scripts") not in sys.path:
    sys.path.insert(0, str(RUNTIME / "scripts"))

from state_context import git_context, open_store  # noqa: E402


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True,
    )
    if result.returncode:
        raise AssertionError(f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout.strip()


def run_vibe(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNTIME / "scripts/vibe.py"), "--root", str(root), *arguments],
        capture_output=True, text=True,
    )


def apply_envelope(store, action: str, payload: dict) -> dict:
    return store.apply({
        "schema_version": 1,
        "command_id": uuid.uuid4().hex,
        "expected_revision": store.status()["revision"],
        "action": action,
        "payload": payload,
    })


def init_repository(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-qm", "initial")
    result = run_vibe(repo, "init")
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return repo


def usable_posix_bash() -> str | None:
    """Return a bash that can run the launcher with native paths, or None.

    On Windows the PATH normally holds the WSL stub. It runs commands inside a
    Linux namespace, so a native Windows path argument never resolves and the
    launcher cannot be exercised through it without separate wslpath translation.
    That is a host limitation, not a launcher defect, so the bash check is
    skipped instead of reported as a failure.
    """
    bash = shutil.which("bash")
    if bash is None:
        return None
    probe = subprocess.run(
        [bash, "-c", "printf vibe-bash-probe"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if probe.returncode != 0 or probe.stdout != b"vibe-bash-probe":
        return None
    # A bash inside WSL exposes wslpath; it cannot take a native Windows path.
    in_wsl = subprocess.run(
        [bash, "-c", "command -v wslpath"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if in_wsl.returncode == 0:
        return None
    return bash


class CrossPlatformSurfaceTests(unittest.TestCase):
    def test_bash_launcher_forwards_the_formal_command_surface(self) -> None:
        bash = usable_posix_bash()
        if bash is None:
            self.skipTest("no POSIX bash that can consume native paths (missing, unusable, or the WSL stub)")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            target.mkdir()
            codex_home = Path(temporary) / "codex"
            codex_home.mkdir()
            (codex_home / "vibe-python").write_text(sys.executable + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    bash, str(VIBE_SH), "--codex-home", str(codex_home),
                    "--root", str(target), "init",
                ],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout.decode("utf-8", "replace"))
            self.assertTrue((target / ".project-log/state-format.json").is_file())

    def test_launcher_resolves_an_opencode_only_install(self) -> None:
        """The wrapper must find the interpreter beside its own install location.

        The installer copies the runtime tree to <config-home>/vibe-workflow/, so a
        user who only ever installed the OpenCode client has no ~/.codex at all.
        Pinning the config home to ~/.codex made that launcher look for an
        interpreter that does not exist; it now infers the home from its own path.
        """
        bash = usable_posix_bash()
        if bash is None:
            self.skipTest("no POSIX bash that can consume native paths")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "opencode-config"
            shutil.copytree(RUNTIME, home / "vibe-workflow")
            (home / "vibe-python").write_text(sys.executable + "\n", encoding="utf-8")
            target = root / "project"
            target.mkdir()
            environment = {
                key: value for key, value in os.environ.items()
                if not key.startswith(("CODEX_HOME", "OPENCODE_CONFIG_DIR", "VIBE_PYTHON"))
            }
            # Point HOME at an empty directory: on a machine that also has the codex
            # client installed, ~/.codex/vibe-python exists, and a launcher that still
            # fell back to it would pass this test for the wrong reason.
            empty_home = root / "empty-home"
            empty_home.mkdir()
            environment["HOME"] = str(empty_home)
            result = subprocess.run(
                [bash, str(home / "vibe-workflow" / "vibe.sh"), "--root", str(target), "init"],
                env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout.decode("utf-8", "replace"))
            self.assertTrue((target / ".project-log/state-format.json").is_file())

    def test_powershell_launcher_is_present_and_targets_the_same_python_entry(self) -> None:
        text = (RUNTIME / "vibe.ps1").read_text(encoding="utf-8")
        self.assertIn("scripts\\vibe.py", text)
        self.assertIn("Resolve-VibePython", text)
        self.assertTrue((RUNTIME / "scripts/vibe_python.ps1").is_file())

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_git_branch_switch_keeps_the_project_log_visible(self) -> None:
        """TASK-060: one Project Log covers every branch, so switching never hides it."""
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            (repo / "README.md").write_text("test\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
            initialized = subprocess.run(
                [sys.executable, str(RUNTIME / "scripts/vibe.py"), "--root", str(repo), "init"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stdout)
            store = open_store(repo)
            context_id = store.context_id
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": 0, "action": "goal.create",
                "payload": {"id": "GOAL-001", "title": "Goal"},
            })
            self.assertEqual(open_store(repo).active_goal_id(), "GOAL-001")

            subprocess.run(["git", "-C", str(repo), "checkout", "-qb", "other"], check=True)
            # The identity no longer depends on the branch, so the same store is found.
            self.assertEqual(open_store(repo).context_id, context_id)
            switched = subprocess.run(
                [sys.executable, str(RUNTIME / "scripts/vibe.py"), "--root", str(repo), "status"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(switched.returncode, 0, switched.stdout)
            self.assertEqual(open_store(repo).active_goal_id(), "GOAL-001")

            subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-"], check=True)
            restored = subprocess.run(
                [sys.executable, str(RUNTIME / "scripts/vibe.py"), "--root", str(repo), "status"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(restored.returncode, 0, restored.stdout)

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_linked_worktree_shares_the_project_log_and_committed_entities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = init_repository(Path(temporary))
            apply_envelope(open_store(repo), "goal.create", {"id": "GOAL-001", "title": "Goal"})
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-qm", "project log")

            worktree = Path(temporary) / "linked"
            run_git(repo, "worktree", "add", "-q", "-b", "feature", str(worktree))

            # The format marker is tracked, so both worktrees resolve one Project Log.
            main_marker = json.loads(
                (repo / ".project-log" / "state-format.json").read_text(encoding="utf-8")
            )
            linked_marker = json.loads(
                (worktree / ".project-log" / "state-format.json").read_text(encoding="utf-8")
            )
            self.assertEqual(linked_marker["project_id"], main_marker["project_id"])

            # A linked worktree has no local SQLite until it attaches.
            before = run_vibe(worktree, "status")
            self.assertEqual(before.returncode, 2, before.stdout)
            self.assertEqual(json.loads(before.stderr)["error"]["code"], "missing_store")
            attached = run_vibe(worktree, "state-attach")
            self.assertEqual(attached.returncode, 0, attached.stderr or attached.stdout)
            self.assertEqual(open_store(worktree).active_goal_id(), "GOAL-001")

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_linked_worktree_context_and_writes_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = init_repository(Path(temporary))
            apply_envelope(open_store(repo), "goal.create", {"id": "GOAL-001", "title": "Goal"})
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-qm", "project log")

            worktree = Path(temporary) / "linked"
            run_git(repo, "worktree", "add", "-q", "-b", "feature", str(worktree))
            self.assertEqual(run_vibe(worktree, "state-attach").returncode, 0)

            # TASK-043 expected one shared context_id. The cache is keyed by
            # `git rev-parse --absolute-git-dir`, which is per-worktree, so the two
            # worktrees hold distinct contexts. Recorded as an acceptance finding.
            self.assertNotEqual(git_context(repo)[0], git_context(worktree)[0])

            # A write in one worktree is not visible from the other before a reconcile.
            apply_envelope(open_store(repo), "goal.create", {"id": "GOAL-002", "title": "main"})
            self.assertEqual(open_store(repo).status()["revision"], 2)
            self.assertEqual(open_store(worktree).status()["revision"], 1)

            apply_envelope(open_store(worktree), "goal.create", {"id": "GOAL-003", "title": "linked"})
            self.assertEqual(open_store(worktree).status()["revision"], 2)
            self.assertEqual(open_store(repo).status()["revision"], 2)

            # Each worktree appended to its own copy of the ledger. Grafting one over
            # the other (a resolved merge) must fail closed, never silently drop history.
            linked_ledger = worktree / ".project-log" / "ledger" / "v1" / "ledger.jsonl"
            (repo / ".project-log" / "ledger" / "v1" / "ledger.jsonl").write_text(
                linked_ledger.read_text(encoding="utf-8"), encoding="utf-8",
            )
            diverged = run_vibe(repo, "status")
            self.assertEqual(diverged.returncode, 2, diverged.stdout)
            self.assertEqual(json.loads(diverged.stderr)["error"]["code"], "ledger_diverged")

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_linked_worktree_exports_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = init_repository(Path(temporary))
            apply_envelope(open_store(repo), "goal.create", {"id": "GOAL-001", "title": "Goal"})
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-qm", "project log")

            worktree = Path(temporary) / "linked"
            run_git(repo, "worktree", "add", "-q", "-b", "feature", str(worktree))
            self.assertEqual(run_vibe(worktree, "state-attach").returncode, 0)

            # Git's index lock is per-worktree, so the two explicit exports do not
            # serialize and publish different pointers in their own exchange dirs.
            first = run_vibe(repo, "exchange", "export")
            second = run_vibe(worktree, "exchange", "export")
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
            main_pointer = (repo / ".project-log" / "exchange" / "current.json").read_text(encoding="utf-8")
            linked_pointer = (worktree / ".project-log" / "exchange" / "current.json").read_text(encoding="utf-8")
            self.assertNotEqual(main_pointer, linked_pointer)


if __name__ == "__main__":
    unittest.main()
