"""Agent-owned semantic memory: the two Markdown notes and read-only records.

Covers the ``vibe memory read/sync`` contract (validate before writing, replace
each note atomically, keep the other note untouched, preserve the file mode) and
the read-only ``vibe record show/list/links`` surface. The schema agreement
between ``framework_info`` and ``state_store`` is pinned in test_release_surface.
"""
from __future__ import annotations

import json
import os
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

from project_memory import read_memory, sync_memory  # noqa: E402


def run_vibe(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VIBE), "--root", str(root), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class MemorySyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.log = self.root / ".project-log"
        self.log.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_an_omitted_note_is_left_untouched(self) -> None:
        (self.log / "progress.md").write_text("# original", encoding="utf-8")
        result = sync_memory(self.root, {"current_session": "# Task\nNext action"})
        self.assertEqual(result["updated"], ["current-session.md"])
        notes = read_memory(self.root)
        self.assertEqual(notes["progress"], "# original")
        self.assertEqual(notes["current_session"], "# Task\nNext action")

    def test_an_invalid_payload_writes_nothing(self) -> None:
        # The invalid key is validated before either file is replaced, so a bad
        # payload cannot leave one note updated and the other stale.
        with self.assertRaises(ValueError):
            sync_memory(self.root, {"progress": "# valid", "invalid": "# bad"})
        self.assertFalse((self.log / "progress.md").exists())

    def test_empty_or_wrong_typed_content_is_refused(self) -> None:
        for payload in ({"progress": ""}, {"progress": "   "}, {"progress": 7}, {}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    sync_memory(self.root, payload)
        self.assertFalse((self.log / "progress.md").exists())

    def test_the_existing_file_mode_survives_a_sync(self) -> None:
        # A naive temp-file replace inherits the temp file's 0600 and would
        # silently tighten a shared project note.
        target = self.log / "progress.md"
        target.write_text("# original", encoding="utf-8")
        os.chmod(target, 0o664)
        sync_memory(self.root, {"progress": "# updated"})
        self.assertEqual(target.stat().st_mode & 0o777, 0o664)
        self.assertEqual(target.read_text(encoding="utf-8"), "# updated")

    def test_a_symlinked_note_is_refused(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("# secret", encoding="utf-8")
        (self.log / "progress.md").symlink_to(outside)
        with self.assertRaises(ValueError):
            sync_memory(self.root, {"progress": "# overwrite"})
        self.assertEqual(outside.read_text(encoding="utf-8"), "# secret")

    def test_memory_sync_refuses_an_uninitialized_project(self) -> None:
        other = Path(self.temporary.name) / "no-log"
        other.mkdir()
        with self.assertRaises(ValueError):
            sync_memory(other, {"progress": "# x"})

    def test_cli_read_reports_both_notes(self) -> None:
        sync_memory(self.root, {"current_session": "# a", "progress": "# b"})
        result = run_vibe(self.root, "memory", "read")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["current_session"], "# a")
        self.assertEqual(payload["progress"], "# b")

    def test_cli_sync_reads_the_payload_file(self) -> None:
        payload_file = self.root / "payload.json"
        payload_file.write_text(json.dumps({"progress": "# via cli"}), encoding="utf-8")
        result = run_vibe(self.root, "memory", "sync", "--file", f"@{payload_file}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.log / "progress.md").read_text(encoding="utf-8"), "# via cli")


class RecordReadSurfaceTests(unittest.TestCase):
    def test_record_help_exposes_the_read_only_commands(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VIBE), "record", "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for word in ("show", "list", "links"):
            self.assertIn(word, result.stdout)


if __name__ == "__main__":
    unittest.main()
