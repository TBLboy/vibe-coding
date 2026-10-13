"""Semantic memory and read-only record surface contracts."""
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
    return subprocess.run([sys.executable, str(VIBE), "--root", str(root), *arguments],
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


class MemorySyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.log = self.root / ".project-log"
        self.log.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_omitted_note_is_untouched(self) -> None:
        (self.log / "progress.md").write_text("# original", encoding="utf-8")
        self.assertEqual(sync_memory(self.root, {"current_session": "# next"})["updated"], ["current-session.md"])
        self.assertEqual(read_memory(self.root)["progress"], "# original")

    def test_invalid_payload_writes_nothing(self) -> None:
        with self.assertRaises(ValueError):
            sync_memory(self.root, {"progress": "# valid", "invalid": "# bad"})
        self.assertFalse((self.log / "progress.md").exists())

    def test_empty_and_wrong_typed_content_is_refused(self) -> None:
        for payload in ({"progress": ""}, {"progress": "   "}, {"progress": 7}, {}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                sync_memory(self.root, payload)

    def test_existing_mode_survives_sync(self) -> None:
        target = self.log / "progress.md"
        target.write_text("# old", encoding="utf-8")
        os.chmod(target, 0o664)
        sync_memory(self.root, {"progress": "# new"})
        if os.name != "nt":
            self.assertEqual(target.stat().st_mode & 0o777, 0o664)

    def test_symlinked_note_is_refused(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("# secret", encoding="utf-8")
        try:
            self.log.joinpath("progress.md").symlink_to(outside)
        except OSError as exc:
            if os.name == "nt":
                self.skipTest(f"symlink privilege unavailable: {exc}")
            raise
        with self.assertRaises(ValueError):
            sync_memory(self.root, {"progress": "# overwrite"})
        self.assertEqual(outside.read_text(encoding="utf-8"), "# secret")

    def test_cli_read_and_sync(self) -> None:
        payload_file = self.root / "payload.json"
        payload_file.write_text(json.dumps({"progress": "# via cli"}), encoding="utf-8")
        result = run_vibe(self.root, "memory", "sync", "--file", f"@{payload_file}")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run_vibe(self.root, "memory", "read")
        self.assertEqual(json.loads(result.stdout)["progress"], "# via cli")


class RecordReadSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.assertEqual(run_vibe(self.root, "init").returncode, 0)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_show_list_and_links_are_available(self) -> None:
        created = run_vibe(self.root, "record", "create", "--kind", "alignment", "--id", "A-001",
                           "--title", "Title", "--status", "open", "--payload", '{"note":"bulk"}')
        self.assertEqual(created.returncode, 0, created.stderr)
        shown = run_vibe(self.root, "record", "show", "--id", "A-001")
        self.assertEqual(json.loads(shown.stdout)["payload"], {"note": "bulk"})
        brief = json.loads(run_vibe(self.root, "record", "list").stdout)
        self.assertNotIn("payload", brief[0])
        full = json.loads(run_vibe(self.root, "record", "list", "--full").stdout)
        self.assertEqual(full[0]["payload"], {"note": "bulk"})


if __name__ == "__main__":
    unittest.main()
