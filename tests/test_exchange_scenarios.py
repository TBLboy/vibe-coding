"""TASK-043: explicit snapshot exchange windows, recovery and Git context.

Covers ``runtime/scripts/state_exchange.py`` and the ``vibe exchange`` surface:

* the export contract on a fresh project;
* the double-clone round trip (attach first, then export, then import);
* adversarial rejections: foreign snapshot, diverged base, unpublished local
  commands and a missing snapshot;
* an interrupted export window (pending export) and operator recovery;
* SIGKILL during the export window, plus the atomic-publish contract that keeps
  a killed payload write from ever leaving a truncated object behind;
* the exchange ``.gitattributes`` line-ending pin;
* source-tree cleanliness for the whole flow.

Every temporary project is created under ``tempfile.TemporaryDirectory``; the
Vibe source tree is never written to.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import open_store, publish_snapshot  # noqa: E402
from state_exchange import SNAPSHOT_NAME  # noqa: E402
from state_exchange import directory as exchange_directory  # noqa: E402
from state_exchange import git_index_lock, read_pointer  # noqa: E402
from state_store import StateError  # noqa: E402


HEX64 = re.compile(r"^[0-9a-f]{64}$")


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True,
    )
    if result.returncode:
        raise AssertionError(f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout.strip()


def make_repository(base: Path, name: str = "repo") -> Path:
    repo = base / name
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-qm", "initial")
    return repo


def apply_envelope(store, action: str, payload: dict, command_id: str | None = None) -> dict:
    return store.apply({
        "schema_version": 1,
        "command_id": command_id or uuid.uuid4().hex,
        "expected_revision": store.status()["revision"],
        "action": action,
        "payload": payload,
    })


def vibe_run(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "vibe.py"), "--root", str(root), *arguments],
        capture_output=True, text=True,
    )


def payload_files(root: Path) -> list[Path]:
    objects = exchange_directory(root) / "objects"
    return sorted(objects.glob("*.payload.json")) if objects.is_dir() else []


def kill_after_marker(script: str, marker: Path, timeout: float = 15.0) -> subprocess.Popen:
    """Run ``script`` and SIGKILL it once it writes ``marker``."""
    process = subprocess.Popen([sys.executable, "-c", script])
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if marker.exists() or process.poll() is not None:
                break
            time.sleep(0.02)
        process.kill()
        process.wait(timeout=15)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=15)
    return process


@unittest.skipUnless(shutil.which("git"), "git is required for the exchange scenarios")
class ExchangeScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = make_repository(self.base, "origin")
        self.vibe_ok(self.repo, "init")
        self.project_id = json.loads(
            (self.repo / ".project-log" / "state-format.json").read_text(encoding="utf-8")
        )["project_id"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    # -- helpers ---------------------------------------------------------
    def vibe(self, root: Path, *arguments: str) -> subprocess.CompletedProcess:
        return vibe_run(root, *arguments)

    def vibe_ok(self, root: Path, *arguments: str) -> dict:
        result = self.vibe(root, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def vibe_error(self, root: Path, *arguments: str) -> str:
        result = self.vibe(root, *arguments)
        self.assertEqual(result.returncode, 2, result.stdout or result.stderr)
        return json.loads(result.stderr)["error"]["code"]

    def seed_goal(self, root: Path, goal_id: str = "GOAL-001") -> int:
        store = open_store(root)
        apply_envelope(store, "goal.create", {"id": goal_id, "title": goal_id})
        return open_store(root).status()["local_revision"]

    def commit_all(self, root: Path, message: str = "snapshot") -> None:
        run_git(root, "add", "-A")
        run_git(root, "commit", "-qm", message)

    # -- 1. export contract ---------------------------------------------
    def test_exchange_status_starts_at_zero_and_export_writes_the_objects(self) -> None:
        initial = self.vibe_ok(self.repo, "exchange", "status")
        self.assertIsNone(initial["snapshot_id"])
        self.assertIsNone(initial["base_snapshot"])
        self.assertEqual(initial["exported_local_revision"], 0)
        self.assertEqual(initial["local_revision"], 0)
        self.assertEqual(initial["unexported_commands"], 0)
        self.assertIsNone(initial["pending_kind"])
        self.assertIsNone(initial["pending_snapshot"])

        revision = self.seed_goal(self.repo)
        exported = self.vibe_ok(self.repo, "exchange", "export")
        self.assertEqual(exported["status"], "exported")
        self.assertRegex(exported["snapshot_id"], HEX64)
        self.assertEqual(exported["exported_local_revision"], revision)

        after = self.vibe_ok(self.repo, "exchange", "status")
        self.assertEqual(after["snapshot_id"], exported["snapshot_id"])
        self.assertEqual(after["exported_local_revision"], after["local_revision"])
        self.assertEqual(after["unexported_commands"], 0)

        exchange = exchange_directory(self.repo)
        self.assertTrue((exchange / "current.json").is_file())
        pointer = read_pointer(self.repo)
        self.assertEqual(pointer["snapshot_id"], exported["snapshot_id"])
        manifest_path = exchange / "objects" / f"{exported['snapshot_id']}.manifest.json"
        payload_path = exchange / "objects" / f"{exported['data_sha256']}.payload.json"
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(payload_path.is_file())
        # A SIGKILL cannot run the cleanup, so the exchange directory must carry an
        # ignore rule for the temporary file a killed publish leaves behind.
        ignore = exchange / ".gitignore"
        self.assertTrue(ignore.is_file(), "the exchange directory has no ignore rule")
        self.assertIn(".tmp-", ignore.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["snapshot_id"], exported["snapshot_id"])
        self.assertEqual(manifest["project_id"], self.project_id)

    def test_exchange_directory_pins_line_endings_for_git(self) -> None:
        attributes = exchange_directory(self.repo) / ".gitattributes"
        self.assertTrue(attributes.is_file())
        # Exactly "* -text": Git must not normalize the canonical single-line objects.
        self.assertEqual(attributes.read_text(encoding="utf-8").strip(), "* -text")

    # -- 2. double-clone round trip -------------------------------------
    def test_double_clone_round_trip_requires_attach_then_export(self) -> None:
        revision = self.seed_goal(self.repo)
        self.vibe_ok(self.repo, "exchange", "export")
        self.commit_all(self.repo)

        clone = self.base / "clone"
        subprocess.run(["git", "clone", "-q", str(self.repo), str(clone)], check=True)

        # A fresh clone has no local SQLite: the ledger is replayed by state-attach.
        missing = self.vibe_error(clone, "status")
        self.assertEqual(missing, "missing_store")
        attach = self.vibe_ok(clone, "state-attach")
        self.assertEqual(attach["attach"]["appended"], revision)
        self.assertEqual(open_store(clone).active_goal_id(), "GOAL-001")

        # The clone sees the committed snapshot pointer but no local export bookkeeping.
        clone_status = self.vibe_ok(clone, "exchange", "status")
        origin_status = self.vibe_ok(self.repo, "exchange", "status")
        self.assertEqual(clone_status["snapshot_id"], origin_status["snapshot_id"])
        self.assertIsNone(clone_status["base_snapshot"])
        self.assertEqual(clone_status["exported_local_revision"], 0)
        self.assertEqual(clone_status["local_revision"], revision)
        self.assertEqual(clone_status["unexported_commands"], revision)

        # Importing before a local export must be refused, not silently overwrite.
        self.assertEqual(self.vibe_error(clone, "exchange", "import"), "unexported_changes")

        # Exporting aligns the bookkeeping, then the same snapshot is a no-op import.
        self.vibe_ok(clone, "exchange", "export")
        aligned = self.vibe_ok(clone, "exchange", "status")
        self.assertEqual(aligned["base_snapshot"], aligned["snapshot_id"])
        self.assertEqual(aligned["unexported_commands"], 0)

        imported = self.vibe_ok(clone, "exchange", "import")
        self.assertEqual(imported["status"], "unchanged")
        self.assertEqual(imported["imported_commands"], 0)
        self.assertEqual(imported["local_revision"], revision)
        self.assertEqual(open_store(clone).active_goal_id(), "GOAL-001")

    def test_import_without_a_published_snapshot_reports_missing(self) -> None:
        self.seed_goal(self.repo)
        self.assertEqual(self.vibe_error(self.repo, "exchange", "import"), "snapshot_missing")

    # -- 3. adversarial rejections --------------------------------------
    def test_import_rejects_a_snapshot_from_another_project(self) -> None:
        self.seed_goal(self.repo)
        self.vibe_ok(self.repo, "exchange", "export")

        foreign = make_repository(self.base, "foreign")
        self.vibe_ok(foreign, "init")
        self.seed_goal(foreign, "GOAL-001")

        # Publish a valid snapshot in the foreign project and graft its exchange
        # directory onto the subject; the manifest digest stays valid, only the
        # project identity differs.
        self.vibe_ok(foreign, "exchange", "export")
        subject_exchange = exchange_directory(self.repo)
        shutil.rmtree(subject_exchange)
        shutil.copytree(exchange_directory(foreign), subject_exchange)

        self.assertEqual(self.vibe_error(self.repo, "exchange", "import"), "foreign_snapshot")
        # Rejection leaves the local store untouched and consistent.
        self.assertEqual(open_store(self.repo).validate(), [])

    def test_import_rejects_a_base_outside_the_snapshot_ancestry(self) -> None:
        self.seed_goal(self.repo)
        self.vibe_ok(self.repo, "exchange", "export")
        before = open_store(self.repo).status()["local_revision"]

        # Force a recorded common base that is not an ancestor of the pointer.
        connection = sqlite3.connect(str(open_store(self.repo).path))
        try:
            connection.execute(
                "UPDATE exchange SET base_snapshot = ? WHERE singleton = 1", ("a" * 64,),
            )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(self.vibe_error(self.repo, "exchange", "import"), "snapshot_diverged")
        store = open_store(self.repo)
        self.assertEqual(store.status()["local_revision"], before)
        self.assertEqual(store.validate(), [])

    # -- 4. interrupted export window -----------------------------------
    def test_interrupted_export_window_is_reported_and_recoverable(self) -> None:
        revision = self.seed_goal(self.repo)
        store = open_store(self.repo)
        snapshot_id = "d" * 64
        store.begin_export(snapshot_id, revision)

        pending = self.vibe_ok(self.repo, "exchange", "status")
        self.assertEqual(pending["pending_kind"], "export")
        self.assertEqual(pending["pending_snapshot"], snapshot_id)
        self.assertIsNone(pending["snapshot_id"])
        self.assertEqual(open_store(self.repo).validate(), [])

        # Observed behavior: ordinary writes are NOT blocked by a pending export.
        # The publication intent only guards the exchange bookkeeping; the next
        # command advances local_revision while pending_revision stays at the
        # snapshot revision.
        reopened = open_store(self.repo)
        apply_envelope(reopened, "goal.create", {"id": "GOAL-002", "title": "second"})
        self.assertEqual(open_store(self.repo).status()["local_revision"], revision + 1)

        # Without a published pointer there is nothing to acknowledge.
        self.assertEqual(self.vibe_error(self.repo, "exchange", "finish"), "exchange_conflict")

        abandoned = self.vibe_ok(self.repo, "exchange", "abandon", "--reason", "test recovery")
        self.assertEqual(abandoned["status"], "abandoned")
        recovered = self.vibe_ok(self.repo, "exchange", "status")
        self.assertIsNone(recovered["pending_kind"])
        self.assertIsNone(recovered["pending_snapshot"])
        self.assertEqual(recovered["unexported_commands"], revision + 1)
        self.assertEqual(open_store(self.repo).validate(), [])

    def test_acknowledge_recovers_an_export_interrupted_after_the_pointer(self) -> None:
        from unittest import mock

        from state_store import Store

        self.seed_goal(self.repo)

        def crash(self, *arguments, **keywords):
            raise RuntimeError("simulated crash after the pointer, before finish")

        with mock.patch.object(Store, "finish_export", crash):
            with self.assertRaises(RuntimeError):
                publish_snapshot(self.repo)

        interrupted = self.vibe_ok(self.repo, "exchange", "status")
        self.assertEqual(interrupted["pending_kind"], "export")
        self.assertEqual(interrupted["snapshot_id"], interrupted["pending_snapshot"])
        self.assertEqual(interrupted["exported_local_revision"], 0)

        acknowledged = self.vibe_ok(self.repo, "exchange", "finish")
        self.assertEqual(acknowledged["status"], "acknowledged")
        self.assertEqual(acknowledged["snapshot_id"], interrupted["pending_snapshot"])

        recovered = self.vibe_ok(self.repo, "exchange", "status")
        self.assertIsNone(recovered["pending_kind"])
        self.assertIsNone(recovered["pending_snapshot"])
        self.assertEqual(recovered["base_snapshot"], recovered["snapshot_id"])
        self.assertEqual(recovered["unexported_commands"], 0)
        self.assertEqual(open_store(self.repo).validate(), [])

    def test_external_git_index_lock_blocks_export_and_is_released(self) -> None:
        self.seed_goal(self.repo)
        with git_index_lock(self.repo):
            with self.assertRaises(StateError) as caught:
                publish_snapshot(self.repo)
            self.assertEqual(caught.exception.code, "git_busy")

        # The failed publication must not strand a pending export.
        after = self.vibe_ok(self.repo, "exchange", "status")
        self.assertIsNone(after["pending_kind"])
        self.assertEqual(open_store(self.repo).validate(), [])

        exported = self.vibe_ok(self.repo, "exchange", "export")
        self.assertEqual(exported["status"], "exported")

    # -- 5. SIGKILL ------------------------------------------------------
    def test_sigkill_in_the_export_window_leaves_a_recoverable_pending_state(self) -> None:
        revision = self.seed_goal(self.repo)
        marker = self.base / "pending.marker"
        snapshot_id = "e" * 64
        script = textwrap.dedent(f"""
            import sys, time
            from pathlib import Path
            sys.path.insert(0, {str(SCRIPTS)!r})
            from state_context import open_store
            store = open_store(Path({str(self.repo)!r}))
            store.begin_export({snapshot_id!r}, store.status()["local_revision"])
            Path({str(marker)!r}).write_text("ready", encoding="utf-8")
            time.sleep(120)
        """)
        process = kill_after_marker(script, marker)
        self.assertTrue(marker.exists(), "the child never reached the export window")
        self.assertIsNotNone(process.poll(), "the child was not killed")

        pending = self.vibe_ok(self.repo, "exchange", "status")
        self.assertEqual(pending["pending_kind"], "export")
        self.assertEqual(pending["pending_snapshot"], snapshot_id)
        self.assertEqual(pending["local_revision"], revision)
        self.assertEqual(open_store(self.repo).validate(), [])
        # No pointer and no manifest were published, so no payload may be referenced.
        self.assertIsNone(read_pointer(self.repo))
        for path in payload_files(self.repo):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except ValueError as error:
                self.fail(f"unpublished payload {path.name} is not parseable: {error}")

        self.vibe_ok(self.repo, "exchange", "abandon", "--reason", "killed window")
        recovered = self.vibe_ok(self.repo, "exchange", "status")
        self.assertIsNone(recovered["pending_kind"])
        self.assertEqual(open_store(self.repo).validate(), [])

    def test_write_exclusive_never_exposes_a_partial_object(self) -> None:
        """A kill during the payload write can only leave a temporary file.

        The bytes are fsynced to a sibling temporary file and linked into place,
        so a reader observes either no object or the complete object; a later
        export of the same revision can no longer trip over a truncated orphan.
        """
        from state_exchange import _write_exclusive

        objects = exchange_directory(self.repo) / "objects"
        objects.mkdir(parents=True, exist_ok=True)
        content = b'{"schema_version": 1}'
        target = objects / f"{'a' * 64}.payload.json"

        # The final name must stay invisible while the bytes are being written.
        seen: list[bool] = []
        real_link = os.link

        def observing_link(source, destination):
            seen.append(Path(destination).exists())
            return real_link(source, destination)

        with mock.patch("state_exchange.os.link", observing_link):
            _write_exclusive(target, content)
        self.assertEqual(seen, [False], "the object was visible before it was complete")
        self.assertEqual(target.read_bytes(), content)
        self.assertEqual(list(objects.glob("*.tmp-*")), [], "a temporary file was left behind")

        # An interrupted publish must leave neither the object nor a temporary file.
        interrupted = objects / f"{'b' * 64}.payload.json"
        with mock.patch("state_exchange.os.link", side_effect=OSError("killed mid-publish")):
            with self.assertRaises(OSError):
                _write_exclusive(interrupted, content)
        self.assertFalse(interrupted.exists(), "a partial object survived the interrupted publish")
        self.assertEqual(list(objects.glob("*.tmp-*")), [])

        # Republishing identical bytes is idempotent; different bytes fail closed.
        _write_exclusive(target, content)
        with self.assertRaises(StateError) as caught:
            _write_exclusive(target, b'{"schema_version": 2}')
        self.assertEqual(caught.exception.code, "snapshot_conflict")

    def test_killed_publish_temporaries_stay_out_of_git_status(self) -> None:
        """A temporary file a kill leaves behind must not surface in `git status`.

        Both the object write and the pointer write name their temporary file with
        ``TEMP_SUFFIX``, so one ignore rule in the exchange directory covers both.
        """
        self.seed_goal(self.repo)
        self.vibe_ok(self.repo, "exchange", "export")
        exchange = exchange_directory(self.repo)
        orphans = [
            exchange / f".{SNAPSHOT_NAME}.tmp-deadbeef",
            exchange / "objects" / f"{'c' * 64}.payload.json.tmp-deadbeef",
        ]
        for orphan in orphans:
            orphan.write_text("orphan\n", encoding="utf-8")
        status = subprocess.run(
            ["git", "-C", str(self.repo), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout
        for orphan in orphans:
            self.assertNotIn(
                orphan.name, status, f"{orphan.name} surfaced in git status instead of being ignored"
            )


@unittest.skipUnless(shutil.which("git"), "git is required for the exchange scenarios")
class SourceTreeCleanlinessTests(unittest.TestCase):
    def source_status(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_a_full_exchange_run_leaves_the_source_tree_unchanged(self) -> None:
        before = self.source_status()
        self.assertFalse(
            (ROOT / ".project-log").exists(),
            "the Vibe source repository must not carry a Project Log",
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = make_repository(base, "origin")
            self.assertEqual(vibe_run(repo, "init").returncode, 0)
            apply_envelope(
                open_store(repo), "goal.create", {"id": "GOAL-001", "title": "Goal"},
            )
            self.assertEqual(vibe_run(repo, "exchange", "export").returncode, 0)
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-qm", "snapshot")

            clone = base / "clone"
            subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
            self.assertEqual(vibe_run(clone, "state-attach").returncode, 0)
            self.assertEqual(vibe_run(clone, "exchange", "export").returncode, 0)
            imported = vibe_run(clone, "exchange", "import")
            self.assertEqual(imported.returncode, 0, imported.stderr)

        after = self.source_status()
        self.assertEqual(after, before, "the exchange run polluted the Vibe source tree")
        self.assertFalse((ROOT / ".project-log").exists())


if __name__ == "__main__":
    unittest.main()
