"""TASK-043: launcher and branch-context checks available on this host."""
from __future__ import annotations

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

from state_context import open_store  # noqa: E402


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

    def test_powershell_launcher_is_present_and_targets_the_same_python_entry(self) -> None:
        text = (RUNTIME / "vibe.ps1").read_text(encoding="utf-8")
        self.assertIn("scripts\\vibe.py", text)
        self.assertIn("Resolve-VibePython", text)
        self.assertTrue((RUNTIME / "scripts/vibe_python.ps1").is_file())

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_git_branch_switch_gets_an_isolated_context(self) -> None:
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
            store.apply({
                "schema_version": 1, "command_id": uuid.uuid4().hex,
                "expected_revision": 0, "action": "goal.create",
                "payload": {"id": "GOAL-001", "title": "Goal"},
            })
            self.assertEqual(open_store(repo).active_goal_id(), "GOAL-001")

            subprocess.run(["git", "-C", str(repo), "checkout", "-qb", "other"], check=True)
            switched = subprocess.run(
                [sys.executable, str(RUNTIME / "scripts/vibe.py"), "--root", str(repo), "status"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertNotEqual(switched.returncode, 0)
            self.assertIn("missing_store", switched.stdout)

            subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-"], check=True)
            restored = subprocess.run(
                [sys.executable, str(RUNTIME / "scripts/vibe.py"), "--root", str(repo), "status"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(restored.returncode, 0, restored.stdout)


if __name__ == "__main__":
    unittest.main()
