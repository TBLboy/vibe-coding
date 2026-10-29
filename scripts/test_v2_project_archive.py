from __future__ import annotations
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/a-project-archive/scripts/archive_v2.py"
SPEC = importlib.util.spec_from_file_location("archive_v2", SCRIPT)
assert SPEC and SPEC.loader
archive_v2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive_v2)


class ArchiveTests(unittest.TestCase):
    def make_project(self, parent: Path) -> Path:
        project = parent / "demo"
        (project / ".vibe/sessions/ses-a").mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (project / ".vibe/progress.md").write_text("# Progress\n", encoding="utf-8")
        (project / ".vibe/sessions/ses-a/current-session.md").write_text("# Resume\n", encoding="utf-8")
        (project / "unrelated.txt").write_text("must not archive\n", encoding="utf-8")
        return project

    def test_archives_only_v2_memory_and_optional_agents_with_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root)
            target = archive_v2.archive(project, root / "archives", datetime(2026, 10, 19, tzinfo=timezone.utc))
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue((target / ".vibe/progress.md").is_file())
            self.assertTrue((target / ".vibe/sessions/ses-a/current-session.md").is_file())
            self.assertFalse((target / "unrelated.txt").exists())
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["format"], "vibe-v2-project-archive-1")
            self.assertEqual({entry["path"] for entry in manifest["files"]}, {
                "AGENTS.md", ".vibe/progress.md", ".vibe/sessions/ses-a/current-session.md",
            })
            self.assertEqual((project / "unrelated.txt").read_text(encoding="utf-8"), "must not archive\n")

    def test_rejects_missing_memory_and_destination_inside_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = root / "empty"; empty.mkdir()
            with self.assertRaisesRegex(ValueError, "Missing .vibe"):
                archive_v2.archive(empty, root / "archives")
            project = self.make_project(root)
            with self.assertRaisesRegex(ValueError, "outside project_root"):
                archive_v2.archive(project, project / "archives")

    def test_never_overwrites_an_existing_timestamped_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); project = self.make_project(root); now = datetime(2026, 10, 19, tzinfo=timezone.utc)
            first = archive_v2.archive(project, root / "archives", now)
            second = archive_v2.archive(project, root / "archives", now)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_dir()); self.assertTrue(second.is_dir())

    def test_remembered_archive_root_is_saved_once_and_reused(self):
        import subprocess, sys as _sys
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); project = self.make_project(root)
            dest = root / "kb"; dest.mkdir()
            conf = root / "archive_root.conf"
            env = {"PYTHONPATH": ""}
            # monkeypatch CONFIG_FILE via a tiny wrapper so the real installed conf is never touched
            wrapper = root / "run.py"
            wrapper.write_text(
                "import importlib.util, sys\n"
                f"spec = importlib.util.spec_from_file_location('a', {str(SCRIPT)!r}); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                f"m.CONFIG_FILE = __import__('pathlib').Path({str(conf)!r})\n"
                "sys.exit(m.main())\n", encoding="utf-8")
            run = lambda *a: subprocess.run([_sys.executable, str(wrapper), *a], capture_output=True, text=True)
            first = run("--project-root", str(project))
            self.assertEqual(first.returncode, archive_v2.EXIT_UNCONFIGURED)
            self.assertIn("No archive root is configured", first.stderr)
            self.assertFalse(conf.exists())
            second = run("--set-archive-root", str(dest), "--project-root", str(project))
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(conf.read_text(encoding="utf-8").strip(), str(dest.resolve()))
            third = run("--project-root", str(project))
            self.assertEqual(third.returncode, 0, third.stderr)
            self.assertTrue(json.loads(third.stdout)["archive"].startswith(str(dest.resolve())))
            self.assertEqual(len(list((dest / "demo").iterdir())), 2)
            bad = run("--set-archive-root", "relative/dir")
            self.assertEqual(bad.returncode, 1)
            missing = run("--set-archive-root", str(root / "nope"))
            self.assertEqual(missing.returncode, 1)

if __name__ == "__main__": unittest.main()
