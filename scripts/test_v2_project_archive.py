from __future__ import annotations
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
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
            _, dest = self.make_publishing_repo(root)
            conf = root / "archive_root.conf"
            # monkeypatch CONFIG_FILE via a tiny wrapper so the real installed conf is never touched
            wrapper = root / "run.py"
            wrapper.write_text(
                "import importlib.util, sys\n"
                f"spec = importlib.util.spec_from_file_location('a', {str(SCRIPT)!r}); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                f"m.CONFIG_FILE = __import__('pathlib').Path({str(conf)!r})\n"
                "sys.exit(m.main())\n", encoding="utf-8")
            run = lambda *a: subprocess.run([_sys.executable, str(wrapper), *a], capture_output=True, text=True, env=self.git_env())
            first = run("--project-root", str(project))
            self.assertEqual(first.returncode, archive_v2.EXIT_UNCONFIGURED)
            self.assertIn("No archive root is configured", first.stderr)
            self.assertFalse(conf.exists())
            second = run("--set-archive-root", str(dest), "--project-root", str(project))
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(conf.read_text(encoding="utf-8").strip(), str(dest.resolve()))
            third = run("--project-root", str(project))
            self.assertEqual(third.returncode, 0, third.stderr)
            third_result = json.loads(third.stdout.strip().splitlines()[-1])
            self.assertTrue(third_result["archive"].startswith(str(dest.resolve())))
            self.assertEqual(third_result["publish"]["status"], "pushed")
            self.assertEqual(len(list((dest / "demo").iterdir())), 2)
            bad = run("--set-archive-root", "relative/dir")
            self.assertEqual(bad.returncode, 1)
            missing = run("--set-archive-root", str(root / "nope"))
            self.assertEqual(missing.returncode, 1)

    def make_publishing_repo(self, parent: Path) -> tuple[Path, Path]:
        """Return (bare remote, archive work tree) with a first commit already pushed."""
        env = self.git_env()
        remote = parent / "remote.git"
        work = parent / "archives"
        self.assertEqual(subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], env=env).returncode, 0)
        self.assertEqual(subprocess.run(["git", "init", "-q", "-b", "main", str(work)], env=env).returncode, 0)
        for key, value in (("user.name", "Archive Test"), ("user.email", "archive@example.invalid")):
            subprocess.run(["git", "-C", str(work), "config", key, value], env=env, check=True)
        (work / "README.md").write_text("archive store\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(work), "add", "README.md"], env=env, check=True)
        subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "init"], env=env, check=True)
        subprocess.run(["git", "-C", str(work), "remote", "add", "origin", str(remote)], env=env, check=True)
        subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "HEAD:main"], env=env, check=True)
        return remote, work

    def git_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update({
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Archive Test",
            "GIT_AUTHOR_EMAIL": "archive@example.invalid",
            "GIT_COMMITTER_NAME": "Archive Test",
            "GIT_COMMITTER_EMAIL": "archive@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        })
        return env

    def test_snapshot_is_committed_and_pushed_then_confirmed_on_the_remote(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, work = self.make_publishing_repo(root)
            project = self.make_project(root)
            target = archive_v2.archive(project, work, datetime(2026, 10, 19, tzinfo=timezone.utc))

            report = archive_v2.push(target)
            self.assertEqual(report["status"], "pushed", report)
            self.assertEqual(report["remote"], "origin")
            self.assertEqual(report["branch"], "main")

            # the remote ref is the local commit: the snapshot really reached the remote
            local = subprocess.run(["git", "-C", str(work), "rev-parse", "HEAD"], capture_output=True, text=True, env=self.git_env()).stdout.strip()
            self.assertEqual(report["commit"], local)
            listing = subprocess.run(
                ["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main"],
                capture_output=True, text=True, env=self.git_env(), check=True,
            ).stdout
            relative = Path(report["snapshot"])
            self.assertIn((relative / "manifest.json").as_posix(), listing)
            self.assertIn((relative / ".vibe/progress.md").as_posix(), listing)

            # a second push finds nothing new to publish
            self.assertEqual(archive_v2.push(target)["status"], "already-published")

    def test_unrelated_files_in_the_archive_repository_are_never_committed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, work = self.make_publishing_repo(root)
            project = self.make_project(root)
            (work / "stray.txt").write_text("not mine\n", encoding="utf-8")
            target = archive_v2.archive(project, work, datetime(2026, 10, 19, tzinfo=timezone.utc))
            report = archive_v2.push(target)
            self.assertEqual(report["status"], "pushed", report)
            changed = subprocess.run(
                ["git", "-C", str(work), "show", "--name-only", "--pretty=format:", "HEAD"],
                capture_output=True, text=True, env=self.git_env(), check=True,
            ).stdout.split()
            self.assertTrue(changed)
            self.assertTrue(all(path.startswith(report["snapshot"]) for path in changed), changed)
            self.assertNotIn("stray.txt", changed)

    def test_reports_why_a_snapshot_could_not_be_pushed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root)
            plain = root / "plain-archives"; plain.mkdir()
            target = archive_v2.archive(project, plain, datetime(2026, 10, 19, tzinfo=timezone.utc))
            self.assertEqual(archive_v2.push(target)["status"], "not-a-repository")

            local_only = root / "local-only"
            env = self.git_env()
            subprocess.run(["git", "init", "-q", "-b", "main", str(local_only)], env=env, check=True)
            target = archive_v2.archive(project, local_only, datetime(2026, 10, 19, tzinfo=timezone.utc))
            self.assertEqual(archive_v2.push(target)["status"], "no-remote")

    def test_an_ignored_snapshot_is_reported_instead_of_silently_unpublished(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, work = self.make_publishing_repo(root)
            env = self.git_env()
            (work / ".gitignore").write_text("demo/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(work), "add", ".gitignore"], env=env, check=True)
            subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "ignore snapshots"], env=env, check=True)
            subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "HEAD:main"], env=env, check=True)
            project = self.make_project(root)
            target = archive_v2.archive(project, work, datetime(2026, 10, 19, tzinfo=timezone.utc))
            with self.assertRaisesRegex(ValueError, "ignores"):
                archive_v2.push(target)

    def test_command_line_exits_four_when_the_snapshot_could_not_be_pushed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root)
            dest = root / "kb"; dest.mkdir()
            conf = root / "archive_root.conf"
            wrapper = root / "run.py"
            wrapper.write_text(
                "import importlib.util, sys\n"
                f"spec = importlib.util.spec_from_file_location('a', {str(SCRIPT)!r}); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                f"m.CONFIG_FILE = __import__('pathlib').Path({str(conf)!r})\n"
                "sys.exit(m.main())\n", encoding="utf-8")

            def run(*arguments: str):
                return subprocess.run([sys.executable, str(wrapper), *arguments], capture_output=True, text=True, env=self.git_env())

            unpushed = run("--set-archive-root", str(dest), "--project-root", str(project))
            self.assertEqual(unpushed.returncode, archive_v2.EXIT_PUSH_FAILED, unpushed.stderr)
            self.assertIn("NOT pushed", unpushed.stderr)
            self.assertEqual(json.loads(unpushed.stdout.strip().splitlines()[-1])["publish"]["status"], "not-a-repository")

            skipped = run("--project-root", str(project), "--no-push")
            self.assertEqual(skipped.returncode, 0, skipped.stderr)
            self.assertEqual(json.loads(skipped.stdout.strip().splitlines()[-1])["publish"]["status"], "skipped")



if __name__ == "__main__": unittest.main()
