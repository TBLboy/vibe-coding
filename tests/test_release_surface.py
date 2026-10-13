"""TASK-044: release identity and install/upgrade/remove safety.

The two install/update/uninstall tests that used to live here drove the codex
installer. That installer is gone; the same invariants (a project log is never
touched, a repeated install is idempotent) are asserted against the OpenCode
installer in tests/test_opencode_installer.py.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = SCRIPTS / "vibe.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from framework_info import STORE_SCHEMA, VERSION  # noqa: E402


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
        # `vibe version` must report the schema the projection actually writes.
        # Asserting the agreement, not a literal, is what stops the two constants
        # from drifting apart again (they disagreed: 3 here, 4 in state_store).
        from state_store import STORE_SCHEMA as PROJECTION_STORE_SCHEMA

        self.assertEqual(payload["store_schema"], PROJECTION_STORE_SCHEMA)
        self.assertEqual(payload["store_schema"], STORE_SCHEMA)
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

if __name__ == "__main__":
    unittest.main()
