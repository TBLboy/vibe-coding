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
    def test_init_rejects_a_git_worktree_root(self) -> None:
        """A plain work folder is the only supported layout (BL-LAYOUT-001/002).

        Before TASK-090 the Git-root branch silently created a second kind of Project
        Log (state under .git/vibe-state). It now fails closed before any write.
        """
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_git(repo, "init", "-q")
            result = run_vibe(repo, "init")
            self.assertEqual(result.returncode, 2, result.stdout)
            payload = json.loads(result.stderr)
            self.assertEqual(payload["error"]["code"], "unsupported_work_layout")
            # The message states the expected layout, so the failure corrects the caller.
            self.assertIn("plain work folder", payload["error"]["message"])
            self.assertIn("repo-a/.git/", payload["error"]["message"])
            # Nothing was written before the refusal.
            self.assertFalse((repo / ".project-log").exists())

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_init_rejects_a_directory_inside_a_git_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_git(repo, "init", "-q")
            nested = repo / "work"
            nested.mkdir()
            result = run_vibe(nested, "init")
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(json.loads(result.stderr)["error"]["code"], "unsupported_work_layout")
            self.assertFalse((nested / ".project-log").exists())

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_nested_repositories_below_a_plain_work_folder_are_allowed(self) -> None:
        """Code repositories live *below* the work folder; that is the supported shape."""
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / "work"
            work.mkdir()
            for name in ("repo-a", "repo-b"):
                child = work / name
                child.mkdir()
                run_git(child, "init", "-q")
            result = run_vibe(work, "init")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((work / ".project-log" / "state-format.json").is_file())
            # The nested repositories are untouched and carry no Project Log of their own.
            for name in ("repo-a", "repo-b"):
                self.assertTrue((work / name / ".git").exists())
                self.assertFalse((work / name / ".project-log").exists())

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_validate_reports_a_log_that_drifted_into_a_git_root(self) -> None:
        """validate catches a log that ended up under an unsupported layout."""
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_git(repo, "init", "-q")
            log = repo / ".project-log"
            log.mkdir()
            (log / "state-format.json").write_text(
                json.dumps({"format": 2, "project_id": uuid.uuid4().hex}), encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(RUNTIME / "scripts" / "validate_project.py"), "--root", str(repo)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("unsupported work layout", result.stdout)


if __name__ == "__main__":
    unittest.main()
