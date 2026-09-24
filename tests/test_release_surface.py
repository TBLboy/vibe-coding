"""TASK-044: release identity and install/upgrade/remove safety."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = SCRIPTS / "vibe.py"
INSTALLER = ROOT / "scripts" / "global_installer.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from framework_info import VERSION  # noqa: E402


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_vibe(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return run(str(VIBE), "--root", str(root), *arguments)


def tree_digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ReleaseSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_vibe_version_reports_release_identity_and_the_single_format(self) -> None:
        result = run_vibe(self.root, "version")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["framework_version"], VERSION)
        self.assertEqual(payload["default_format"], 2)
        self.assertEqual(payload["store_schema"], 3)
        self.assertEqual(payload["supported_formats"], [2])
        self.assertNotIn("retirement_stages", payload)
        self.assertNotIn("legacy_guidance", payload)

    def test_version_flag_matches_the_version_command(self) -> None:
        flag = run_vibe(self.root, "--version")
        self.assertEqual(flag.returncode, 0, flag.stderr)
        self.assertIn(VERSION, flag.stdout)
        command = run_vibe(self.root, "version")
        self.assertEqual(json.loads(command.stdout)["framework_version"], VERSION)

    def test_release_notes_document_the_single_supported_format(self) -> None:
        notes = (ROOT / "docs/RELEASE-NOTES.md").read_text(encoding="utf-8")
        usage = (ROOT / "docs/USAGE.md").read_text(encoding="utf-8")
        self.assertIn(VERSION, notes)
        self.assertIn("format 2", notes)
        self.assertIn("format 2", usage)
        self.assertNotIn("migrate preview|apply|resume|rollback", usage)

    def test_install_update_uninstall_never_touch_project_logs(self) -> None:
        project = self.root / "work"
        project.mkdir()
        created = run_vibe(project, "init")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        before = tree_digest(project)
        home = self.root / "codex-home"
        outputs: dict[str, str] = {}
        for action in ("install", "update", "uninstall"):
            result = run(
                str(INSTALLER),
                action,
                "--codex-home",
                str(home),
                "--without-mcp",
                "--skip-preflight",
            )
            outputs[action] = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, outputs[action])
            self.assertEqual(tree_digest(project), before, action)
        self.assertIn("format 2", outputs["install"])
        self.assertIn("format 2", outputs["update"])
        self.assertIn("not touched", outputs["uninstall"])

    def test_installer_is_repeatable_and_keeps_the_state_file_consistent(self) -> None:
        home = self.root / "codex-home"
        first = run(str(INSTALLER), "install", "--codex-home", str(home), "--without-mcp", "--skip-preflight")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        state_file = home / ".vibe-codex-installation-state.json"
        first_state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(first_state["package_version"], VERSION)
        self.assertIn("format 2", first.stdout)

        second = run(str(INSTALLER), "install", "--codex-home", str(home), "--without-mcp", "--skip-preflight")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        second_state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(second_state["package_version"], VERSION)
        self.assertEqual(second_state["installed_at"], first_state["installed_at"])


if __name__ == "__main__":
    unittest.main()
