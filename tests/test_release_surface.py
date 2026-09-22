"""TASK-044: release identity, legacy guidance and install/upgrade/remove safety."""
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
LOOPCTL = SCRIPTS / "loopctl.py"
INIT = SCRIPTS / "init_project.py"
INSTALLER = ROOT / "scripts" / "global_installer.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from framework_info import RETIREMENT_STAGES, VERSION  # noqa: E402


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


def run_loopctl(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return run(str(LOOPCTL), "--root", str(root), *arguments)


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

    def legacy_project(self) -> Path:
        project = self.root / "legacy-project"
        project.mkdir()
        created = run(str(INIT), "--target", str(project), "--format", "1")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        return project

    def test_vibe_version_reports_release_identity_and_retirement_gates(self) -> None:
        result = run_vibe(self.root, "version")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["framework_version"], VERSION)
        self.assertEqual(payload["default_format"], 2)
        self.assertEqual(payload["store_schema"], 3)
        self.assertEqual(payload["supported_formats"], [1, 2])
        stages = {stage["id"]: stage for stage in payload["retirement_stages"]}
        self.assertEqual(set(stages), {"stop-writing", "stop-reading", "stop-support"})
        for stage in stages.values():
            self.assertEqual(stage["gate"], "user-approval")
            self.assertEqual(stage["status"], "pending")

    def test_version_flag_matches_the_version_command(self) -> None:
        flag = run_vibe(self.root, "--version")
        self.assertEqual(flag.returncode, 0, flag.stderr)
        self.assertIn(VERSION, flag.stdout)
        command = run_vibe(self.root, "version")
        self.assertEqual(json.loads(command.stdout)["framework_version"], VERSION)

    def test_release_notes_and_usage_document_the_retirement_gates(self) -> None:
        notes = (ROOT / "docs/RELEASE-NOTES.md").read_text(encoding="utf-8")
        usage = (ROOT / "docs/USAGE.md").read_text(encoding="utf-8")
        self.assertIn(VERSION, notes)
        for stage in RETIREMENT_STAGES:
            self.assertIn(stage["id"], notes)
            self.assertIn(stage["id"], usage)
        self.assertIn("用户确认", notes)
        self.assertIn("不会改写任何项目的 `.project-log/`", notes)
        self.assertIn("legacy format: migrate with vibe migrate", usage)

    def test_legacy_project_reads_stay_available_with_migration_guidance(self) -> None:
        project = self.legacy_project()
        status = run_loopctl(project, "--json", "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["format"], 1)
        self.assertTrue(payload["legacy"])
        self.assertIn("migrate with vibe migrate", payload["guidance"])

        validate = run_loopctl(project, "--json", "validate")
        self.assertIn(validate.returncode, (0, 1), validate.stderr)
        validated = json.loads(validate.stdout)
        self.assertEqual(validated["format"], 1)
        self.assertIn("migrate with vibe migrate", validated["guidance"])

        vibe_status = run_vibe(project, "status")
        self.assertEqual(vibe_status.returncode, 0, vibe_status.stderr)
        self.assertIn("Format:      1 (legacy)", vibe_status.stdout)
        self.assertIn("migrate with vibe migrate", vibe_status.stdout)

    def test_legacy_writes_warn_without_becoming_silent(self) -> None:
        project = self.legacy_project()
        active_run = project / ".project-log/loop/active-run.yaml"
        before = active_run.read_text(encoding="utf-8")
        result = run_loopctl(
            project, "--json", "start-run", "--phase", "implementation", "--task-id", "TASK-001"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deprecated", result.stderr)
        self.assertIn("vibe migrate preview", result.stderr)
        self.assertNotEqual(before, active_run.read_text(encoding="utf-8"))
        self.assertFalse((project / ".project-log/state-format.json").exists())

    def test_install_update_uninstall_never_touch_project_logs(self) -> None:
        project = self.legacy_project()
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
        self.assertIn("migrate with vibe migrate", outputs["update"])
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
